"""MFAPIs-owned FX quotation engine.

Does not fetch market rates from Twelve Data, Massive, or any other external rate API.
Accepts quote observations supplied over an authenticated ingestion endpoint, stores them,
computes bid/ask inverses and cross rates, and refuses stale/unavailable quotes.
Actual live updates require a real, authorized quote feed to publish observations.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from typing import Iterable

from sqlalchemy import BigInteger, Column, Integer, String, Table, Text, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .db import metadata

DEFAULT_PAIRS = 'EUR/USD,USD/INR,GBP/USD,USD/JPY,USD/CHF,AUD/USD,USD/CAD,NZD/USD,USD/SGD,USD/HKD,USD/CNY,EUR/GBP,EUR/INR,GBP/INR,AUD/INR,CAD/INR'
NAMES = {'EUR':'Euro','USD':'US dollar','INR':'Indian rupee','GBP':'Pound sterling',
         'JPY':'Japanese yen','CHF':'Swiss franc','AUD':'Australian dollar','CAD':'Canadian dollar',
         'NZD':'New Zealand dollar','SGD':'Singapore dollar','HKD':'Hong Kong dollar','CNY':'Chinese yuan'}
PAIR_PATTERN = re.compile(r'^[A-Z]{3}/[A-Z]{3}$')

# New table names are deliberate: stale values from previous third-party caches
# can never be silently reused by the independently built FX engine.
latest_quotes = Table('mfapis_owned_fx_latest_v1', metadata,
    Column('symbol', String(7), primary_key=True),
    Column('bid', Text, nullable=False), Column('ask', Text, nullable=False),
    Column('observed_at', BigInteger, nullable=False),
    Column('received_at', BigInteger, nullable=False),
    Column('source', String(64), nullable=False),
    Column('raw_sha256', String(64), nullable=False))
quote_history = Table('mfapis_owned_fx_history_v1', metadata,
    Column('event_id', String(64), primary_key=True),
    Column('symbol', String(7), nullable=False),
    Column('bid', Text, nullable=False), Column('ask', Text, nullable=False),
    Column('observed_at', BigInteger, nullable=False),
    Column('received_at', BigInteger, nullable=False),
    Column('source', String(64), nullable=False))

class FXError(Exception):
    def __init__(self, status, code, message, retry_after=0):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


def read_int(name, default, low, high):
    try:
        v = int(os.getenv(name, str(default)))
        if low <= v <= high:
            return v
    except ValueError:
        pass
    raise FXError(503, 'configuration_error', f'Invalid {name}')

@dataclass(frozen=True)
class Settings:
    pairs: tuple[str,...]
    max_quote_age: int
    refresh_seconds: int
    display_authorized: bool
    ingestion_configured: bool

    @classmethod
    def env(cls):
        pairs = tuple(dict.fromkeys(p.strip().upper() for p in os.getenv('FX_ALLOWED_PAIRS', DEFAULT_PAIRS).split(',')))
        if not pairs or len(pairs)>100 or any(not PAIR_PATTERN.fullmatch(p) or p[:3]==p[4:] for p in pairs):
            raise FXError(503, 'configuration_error', 'Invalid FX_ALLOWED_PAIRS')
        return cls(pairs,
                   read_int('FX_MAX_QUOTE_AGE_SECONDS',120,5,86400),
                   read_int('FX_REFRESH_SECONDS',15,5,3600),
                   os.getenv('FX_LIVE_DISPLAY_AUTHORIZED','false').strip().lower()=='true',
                   len(os.getenv('MFAPIS_INGEST_KEY','').strip())>=32)


def capabilities(settings=None):
    s = settings or Settings.env()
    currencies = sorted({c for p in s.pairs for c in p.split('/')})
    return {'provider':'mfapis', 'pricing_engine':'mfapis_owned_fx_v1',
            'configured': s.ingestion_configured and s.display_authorized,
            'ingestion_configured':s.ingestion_configured,
            'public_display_authorized':s.display_authorized,
            'currencies':[{'code':c,'name':NAMES.get(c,c)} for c in currencies],
            'pairs':list(s.pairs), 'inverse_pairs':True, 'cross_rates':True,
            'refresh_seconds':s.refresh_seconds,
            'max_quote_age_seconds':s.max_quote_age,
            'rate_type':'observed_bid_ask_midpoint',
            'note':'MFAPIs owns the API, storage, calculation and display. Fresh live market values are possible only when an authorized quote source sends real observations. This API does not generate market prices.'}


def utc_iso(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).isoformat().replace('+00:00','Z')


def parse_time(observed):
    if isinstance(observed, datetime):
        dt = observed
    elif isinstance(observed, str):
        try: dt=datetime.fromisoformat(observed.replace('Z','+00:00'))
        except ValueError: raise FXError(422,'invalid_timestamp','observed_at must be ISO 8601 UTC with a timezone') from None
    else:
        raise FXError(422,'invalid_timestamp','observed_at must be ISO 8601 UTC with a timezone')
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise FXError(422,'invalid_timestamp','observed_at must include a timezone')
    return int(dt.timestamp())


def normalize_quote(symbol, bid, ask, observed_at, source, now, settings):
    symbol = str(symbol).upper().strip()
    if not PAIR_PATTERN.fullmatch(symbol) or symbol[:3]==symbol[4:]:
        raise FXError(422,'invalid_symbol','Use a valid currency symbol such as USD/INR')
    supported = {p for p in settings.pairs}
    if symbol not in supported and symbol[4:]+'/'+symbol[:3] not in supported:
        raise FXError(422,'unsupported_pair','This currency pair is not enabled')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,63}',source or ''):
        raise FXError(422,'invalid_source','A named, attributable source is required')
    try:
        b=Decimal(str(bid)); a=Decimal(str(ask))
    except Exception:
        raise FXError(422,'invalid_price','Bid and ask must be decimal numbers') from None
    if not b.is_finite() or not a.is_finite() or not (0<b<=a<=Decimal('1000000000000')):
        raise FXError(422,'invalid_price','Expected positive finite bid <= ask')
    ts=parse_time(observed_at)
    if ts>now+5:
        raise FXError(422,'future_quote','Quote timestamp is in the future')
    if now-ts>settings.max_quote_age:
        raise FXError(422,'stale_ingest','Quote is too old to ingest as current')
    # Size bound protects database storage from very long decimal representations.
    bs,as_=str(b),str(a)
    if len(bs)>80 or len(as_)>80:
        raise FXError(422,'invalid_price','Price precision exceeds supported length')
    return {'symbol':symbol, 'bid':bs, 'ask':as_, 'observed_at':ts,
            'received_at':now, 'source':source}


def _insert(engine):
    return pg_insert if engine.dialect.name=='postgresql' else sqlite_insert


def ingest(engine, symbol, bid, ask, observed_at, source, settings=None, clock=time.time):
    """Validate, audit, and persist one real upstream market observation.

    Not an autonomous market-price generator. Call this only from a trusted feed adapter.
    """
    s = settings or Settings.env()
    now=int(clock())
    q=normalize_quote(symbol,bid,ask,observed_at,source,now,s)
    digest=hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    q['raw_sha256']=digest
    stmt=_insert(engine)
    with engine.begin() as conn:
        if conn.dialect.name=='postgresql':
            conn.execute(text('SELECT pg_advisory_xact_lock(hashtext(:lock))'),{'lock':'owned_fx_'+q['symbol']})
        prior=conn.execute(select(latest_quotes).where(latest_quotes.c.symbol==q['symbol'])).mappings().first()
        if prior and q['observed_at'] < prior['observed_at']:
            raise FXError(409,'out_of_order','A newer quote is already stored')
        if prior and q['observed_at'] == prior['observed_at']:
            if (q['bid'],q['ask'],q['source'])!=(prior['bid'],prior['ask'],prior['source']):
                raise FXError(409,'conflicting_timestamp','Conflicting values for an existing quote timestamp')
            return {'status':'duplicate','symbol':q['symbol'],'as_of':utc_iso(q['observed_at'])}
        stmt_latest=stmt(latest_quotes).values(**q)
        conn.execute(stmt_latest.on_conflict_do_update(index_elements=['symbol'],set_={k:getattr(stmt_latest.excluded,k) for k in q if k!='symbol'}))
        event={k:q[k] for k in ('symbol','bid','ask','observed_at','received_at','source')}
        conn.execute(quote_history.insert().values(event_id=digest,**event))
    return {'status':'accepted','symbol':q['symbol'],'as_of':utc_iso(q['observed_at']),'event_id':digest}


def _fresh_edges(engine, settings, now):
    with engine.connect() as conn:
        observations=conn.execute(select(latest_quotes)).mappings().all()
    result={}
    for row in observations:
        if row['symbol'] not in settings.pairs and (row['symbol'][4:]+'/'+row['symbol'][:3]) not in settings.pairs:
            continue
        if not (0<=now-row['observed_at']<=settings.max_quote_age):
            continue
        bid,ask=Decimal(row['bid']),Decimal(row['ask'])
        base,quote=row['symbol'].split('/')
        record={'symbol':row['symbol'],'source':row['source'],'timestamp':row['observed_at'],
                'received_at':row['received_at'],'bid':bid,'ask':ask}
        result[(base,quote)]=record
        with localcontext() as ctx:
            ctx.prec=56
            result[(quote,base)]={**record,'bid':Decimal(1)/ask,'ask':Decimal(1)/bid,'inverse':True}
    return result


def _route(edges, base, quote):
    if (base,quote) in edges:
        return [edges[(base,quote)]]
    # Only one intermediate hop and choose a known currency hub. This avoids
    # potentially misleading arbitrage loops and uncontrolled graph searches.
    for hub in ['USD','EUR','GBP']:
        if hub not in [base,quote] and (base,hub) in edges and (hub,quote) in edges:
            first,second=edges[(base,hub)],edges[(hub,quote)]
            # Prevent joining incompatible or incomparable provider sources.
            if first['source'] == second['source']:
                return [first,second]
    return None


def latest(engine, symbol, settings=None, clock=time.time):
    s=settings or Settings.env()
    if not s.display_authorized:
        raise FXError(503,'redisplay_not_authorized','Live display is disabled until source display rights are confirmed')
    if not s.ingestion_configured:
        raise FXError(503,'feed_not_configured','No authenticated quote feed has been configured')
    symbol=str(symbol).upper().strip()
    if not PAIR_PATTERN.fullmatch(symbol) or symbol[:3]==symbol[4:]:
        raise FXError(422,'invalid_symbol','Expected a pair such as USD/INR')
    base,quote=symbol.split('/')
    if base not in {c for p in s.pairs for c in p.split('/')} or quote not in {c for p in s.pairs for c in p.split('/')}:
        raise FXError(404,'unsupported_currency','This currency is not enabled')
    now=int(clock())
    edges=_fresh_edges(engine,s,now)
    legs=_route(edges,base,quote)
    if not legs:
        # Previous providers' cache tables are intentionally never considered.
        raise FXError(503,'no_fresh_quote','No fresh quote was received from your authorized live feed',s.refresh_seconds)
    with localcontext() as ctx:
        ctx.prec=56
        bid=Decimal(1); ask=Decimal(1)
        for leg in legs:
            bid*=leg['bid']; ask*=leg['ask']
        rate=(bid+ask)/Decimal(2)
    observed=min(l['timestamp'] for l in legs)
    received=max(l['received_at'] for l in legs)
    sources=list(dict.fromkeys(l['source'] for l in legs))
    return {'symbol':symbol,'base':base,'quote':quote,'rate':str(rate),'bid':str(bid),'ask':str(ask),
            'rate_type':'observed_bid_ask_midpoint','provider':'mfapis','source':sources[0],
            'source_observations':sources,'inverse':any(l.get('inverse',False) for l in legs),
            'derived_cross_rate':len(legs)>1,'legs':[l['symbol'] for l in legs],
            'timestamp':observed,'as_of':utc_iso(observed),'fetched_at':utc_iso(received),
            'quote_age_seconds':now-observed,'cached':True, 'mode':'live',
            'note':'MFAPIs-derived midpoint of authorized source observations; informational only, not an executable dealer quote.'}


def available_quotes(engine,settings=None,clock=time.time):
    s=settings or Settings.env()
    if not (s.display_authorized and s.ingestion_configured):
        raise FXError(503,'not_available','Quote listing is not available until an authorized feed is configured')
    now=int(clock())
    with engine.connect() as conn:
        rows=conn.execute(select(latest_quotes).order_by(latest_quotes.c.symbol)).mappings().all()
    return {'provider':'mfapis', 'as_of':utc_iso(now),
            'quotes':[{'symbol':r['symbol'],'source':r['source'],'bid':r['bid'],'ask':r['ask'],
                       'observed_at':utc_iso(r['observed_at']),
                       'age_seconds':now-r['observed_at'],
                       'fresh':0<=now-r['observed_at']<=s.max_quote_age} for r in rows]}


def history(engine,symbol,limit=100):
    s=Settings.env()
    if not (s.display_authorized and s.ingestion_configured):
        raise FXError(503,'not_available','Quote history is not available until an authorized feed is configured')
    with engine.connect() as conn:
        rows=conn.execute(select(quote_history).where(quote_history.c.symbol==symbol).order_by(quote_history.c.observed_at.desc()).limit(limit)).mappings().all()
    return {'symbol':symbol,'data':[{'bid':r['bid'],'ask':r['ask'],'source':r['source'],
        'as_of':utc_iso(r['observed_at']), 'received_at':utc_iso(r['received_at'])} for r in rows]}

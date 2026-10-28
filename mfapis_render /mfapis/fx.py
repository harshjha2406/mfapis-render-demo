"""Latest FX quotes: server-only credentials, persistent cache and credit budgets.

No fallback from a failed latest quote to historical ECB observations.
The provider timestamp always survives caching and inverse-pair calculation.
"""
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext

import requests
from sqlalchemy import BigInteger, Column, Integer, LargeBinary, String, Table, Text, select, text

from .db import metadata
from .http import emit

URL = 'https://api.twelvedata.com/exchange_rate'
DEFAULT_PAIRS = 'EUR/USD,USD/INR,GBP/USD,USD/JPY,USD/CHF,AUD/USD,USD/CAD,NZD/USD,USD/SGD,USD/HKD,USD/CNY,EUR/GBP,EUR/INR,GBP/INR,AUD/INR,CAD/INR'
NAMES = {'EUR':'Euro','USD':'US dollar','INR':'Indian rupee','GBP':'Pound sterling',
         'JPY':'Japanese yen','CHF':'Swiss franc','AUD':'Australian dollar','CAD':'Canadian dollar',
         'NZD':'New Zealand dollar','SGD':'Singapore dollar','HKD':'Hong Kong dollar','CNY':'Chinese yuan'}
quotes = Table('latest_fx_quotes', metadata,
    Column('symbol', String(7), primary_key=True), Column('rate', Text, nullable=False),
    Column('provider_timestamp', BigInteger, nullable=False), Column('fetched_at', BigInteger, nullable=False),
    Column('raw_response', LargeBinary, nullable=False), Column('raw_sha256', String(64), nullable=False))
budget = Table('fx_provider_budget', metadata,
    Column('id', String(30), primary_key=True), Column('window_start', BigInteger, nullable=False),
    Column('used', Integer, nullable=False))
failures = Table('fx_provider_cooldown', metadata,
    Column('symbol', String(20), primary_key=True), Column('retry_at', BigInteger, nullable=False),
    Column('status', Integer, nullable=False), Column('code', String(50), nullable=False),
    Column('message', Text, nullable=False))
# SQLite development runs are single-process. PostgreSQL uses advisory locks too.
_lock = threading.RLock()


class FXError(Exception):
    def __init__(self, status, code, message, retry_after=0):
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after
        super().__init__(message)


def setting(name, default, minimum, maximum):
    try:
        n = int(os.getenv(name, str(default)))
        if not minimum <= n <= maximum:
            raise ValueError()
        return n
    except ValueError:
        raise FXError(503, 'configuration_error', f'Invalid server setting: {name}') from None


@dataclass(frozen=True)
class Settings:
    key: str
    pairs: tuple
    cache_seconds: int
    max_age: int
    minute_limit: int
    day_limit: int

    @classmethod
    def env(cls):
        pairs = tuple(dict.fromkeys(p.strip().upper() for p in os.getenv('FX_ALLOWED_PAIRS', DEFAULT_PAIRS).split(',')))
        if not pairs or len(pairs) > 100 or any(not re.fullmatch(r'[A-Z]{3}/[A-Z]{3}', p) or p[:3] == p[4:] for p in pairs):
            raise FXError(503, 'configuration_error', 'Invalid FX_ALLOWED_PAIRS server setting')
        return cls(os.getenv('TWELVE_DATA_API_KEY', '').strip(), pairs,
                   setting('FX_CACHE_SECONDS', 60, 15, 3600),
                   setting('FX_MAX_QUOTE_AGE_SECONDS', 300, 30, 86400),
                   setting('FX_PROVIDER_REQUESTS_PER_MINUTE', 8, 1, 10000),
                   setting('FX_PROVIDER_REQUESTS_PER_DAY', 800, 1, 10000000))


def capabilities(settings=None):
    s = settings or Settings.env()
    currencies = sorted({c for pair in s.pairs for c in pair.split('/')})
    return {'provider':'twelvedata', 'configured':bool(s.key),
            'currencies':[{'code':c, 'name':NAMES.get(c,c)} for c in currencies],
            'pairs':list(s.pairs), 'inverse_pairs':True,
            'cache_seconds':s.cache_seconds, 'refresh_seconds':max(60,s.cache_seconds),
            'max_quote_age_seconds':s.max_age,
            'note':'Enabled pairs are subject to your provider account coverage. Historical mode uses stored ECB daily reference rates.'}


def advisory(conn, name):
    if conn.dialect.name == 'postgresql':
        conn.execute(text('SELECT pg_advisory_xact_lock(hashtext(:name))'), {'name':name})


def save(conn, table, key, values):
    # Callers hold an advisory lock for this key on PostgreSQL.
    if conn.execute(select(table).where(table.c[list(key)[0]] == list(key.values())[0])).first():
        conn.execute(table.update().where(table.c[list(key)[0]] == list(key.values())[0]).values(**values))
    else:
        conn.execute(table.insert().values(**key, **values))


def reserve_credit(engine, s, now):
    """Reserve each HTTP attempt before network I/O. Survives process restarts."""
    with engine.begin() as conn:
        advisory(conn, 'mfapis_fx_credit_budget')
        cool = conn.execute(select(failures).where(failures.c.symbol == '*')).mappings().first()
        if cool and cool['retry_at'] > now:
            raise FXError(cool['status'], cool['code'], cool['message'], cool['retry_at']-now)
        changes = []
        for period, width, limit in [('minute',60,s.minute_limit),('day',86400,s.day_limit)]:
            start = now // width * width
            old = conn.execute(select(budget).where(budget.c.id == period)).mappings().first()
            used = old['used'] if old and old['window_start'] == start else 0
            if used >= limit:
                raise FXError(429, 'provider_budget_exhausted', 'The shared FX request budget is exhausted. Try again after the indicated delay.', start+width-now)
            changes.append((period,start,used+1))
        for period,start,used in changes:
            save(conn,budget,{'id':period},{'window_start':start,'used':used})


def cooldown(engine, symbol, error, now):
    with engine.begin() as conn:
        advisory(conn, 'mfapis_fx_credit_budget')
        # Also slow down all pairs for authentication/quota failures.
        scope = '*' if error.code in {'provider_rate_limited','provider_authentication'} else symbol
        save(conn, failures, {'symbol':scope}, {'retry_at':now+max(30,error.retry_after),
              'status':error.status,'code':error.code,'message':error.message})


def parse_quote(body, symbol, now):
    try:
        p = json.loads(body, parse_float=Decimal)
    except (ValueError, UnicodeDecodeError):
        raise FXError(502,'invalid_provider_response','The rate provider returned invalid JSON.',30) from None
    if not isinstance(p,dict):
        raise FXError(502,'invalid_provider_response','The rate provider returned an unexpected response.',30)
    if p.get('status') == 'error' or 'code' in p:
        try: code = int(p.get('code',502))
        except (TypeError,ValueError): code = 502
        if code == 429: raise FXError(429,'provider_rate_limited','The rate provider quota has been reached.',60)
        if code in (401,403): raise FXError(503,'provider_authentication','The provider key or account permissions need attention.',60)
        if code in (400,404): raise FXError(404,'pair_unavailable','This currency pair is unavailable for the configured provider account.',60)
        raise FXError(502,'provider_error','The rate provider could not fulfil this request.',30)
    try:
        rate = Decimal(str(p['rate']))
        ts = p['timestamp']
        if (p['symbol'] != symbol or isinstance(ts,bool) or not isinstance(ts,int)
                or ts < 946684800 or ts > now + 30 or not rate.is_finite() or rate <= 0 or rate > Decimal('1e15')):
            raise ValueError()
    except (KeyError,TypeError,ValueError,InvalidOperation):
        raise FXError(502,'invalid_provider_response','The provider rate, symbol or timestamp failed validation.',30) from None
    return {'symbol':symbol, 'rate':str(rate), 'provider_timestamp':ts, 'fetched_at':now,
            'raw_response':body,'raw_sha256':hashlib.sha256(body).hexdigest()}


def fetch_quote(engine, symbol, s, clock=time.time, sleep=time.sleep, session=None):
    """At most two attempts for network/5xx failures. Never retry quota/auth errors."""
    session = session or requests
    for attempt in range(2):
        now = int(clock()); reserve_credit(engine,s,now)
        started = time.monotonic()
        try:
            # Credentials in a header: never in browser JS, query URLs or logs.
            r = session.get(URL,params={'symbol':symbol,'dp':11},
                headers={'Authorization':'apikey '+s.key, 'Accept':'application/json'},
                timeout=(10,10),allow_redirects=False)
            emit('fx_provider_request',source='twelvedata',symbol=symbol,status=r.status_code,
                 attempt=attempt+1,elapsed_ms=round((time.monotonic()-started)*1000))
            if r.status_code == 429:
                try: delay = max(60,min(86400,int(r.headers.get('Retry-After','60'))))
                except ValueError: delay = 60
                raise FXError(429,'provider_rate_limited','The rate provider quota has been reached.',delay)
            if r.status_code in (401,403):
                raise FXError(503,'provider_authentication','The provider key or account permissions need attention.',60)
            if r.status_code in (400,404):
                raise FXError(404,'pair_unavailable','This currency pair is unavailable for the configured provider account.',60)
            if r.status_code >= 500:
                if attempt == 0: sleep(.3); continue
                raise FXError(502,'provider_unavailable','The rate provider is temporarily unavailable.',30)
            if r.status_code != 200 or len(r.content) > 65536:
                raise FXError(502,'invalid_provider_response','Unexpected response from the rate provider.',30)
            return parse_quote(r.content,symbol,int(clock()))
        except requests.RequestException:
            emit('fx_provider_network_error',source='twelvedata',symbol=symbol,attempt=attempt+1)
            if attempt == 0: sleep(.3); continue
            # Do not expose exception text: it may contain authorization details.
            raise FXError(502,'provider_unavailable','The rate provider could not be reached.',30) from None
    raise FXError(502,'provider_unavailable','The rate provider is temporarily unavailable.',30)


def response(record, requested, now, cached, s):
    age = max(0,now-record['provider_timestamp'])
    if age > s.max_age:
        # No successful conversion using a stale quote; still explain last observed time.
        raise FXError(503,'stale_quote',f"The latest provider quote is too old ({age} seconds). Last provider timestamp: {record['provider_timestamp']}. Try again later; historical mode is separate.",s.cache_seconds)
    with localcontext() as ctx:
        ctx.prec = 40
        rate = Decimal(record['rate'])
        inverse = requested != record['symbol']
        if inverse: rate = Decimal(1)/rate
        return {'symbol':requested,'rate':str(rate),'timestamp':record['provider_timestamp'],
                'as_of':datetime.fromtimestamp(record['provider_timestamp'],timezone.utc).isoformat(),
                'fetched_at':datetime.fromtimestamp(record['fetched_at'],timezone.utc).isoformat(),
                'provider':'twelvedata','provider_symbol':record['symbol'],'inverse':inverse,
                'mode':'latest','cached':cached,'quote_age_seconds':age,
                'cache_age_seconds':max(0,now-record['fetched_at']),
                'max_quote_age_seconds':s.max_age,'stale':False,
                'refresh_after_seconds':max(1,s.cache_seconds-(now-record['fetched_at'])),
                'attribution':'Data provided by Twelve Data. Conversion calculated by MFAPIs.'}


def latest(engine, symbol, settings=None, clock=time.time, fetch=fetch_quote):
    s = settings or Settings.env()
    if not s.key:
        raise FXError(503,'provider_not_configured','Latest rates are not configured. Set TWELVE_DATA_API_KEY in the server environment.')
    reverse = '/'.join(reversed(symbol.split('/')))
    # Canonical preference makes EUR/USD and USD/EUR share the same quote/cache entry.
    provider_symbol = next((p for p in s.pairs if p in (symbol,reverse)),None)
    if provider_symbol is None:
        raise FXError(400,'unsupported_pair','This pair is not enabled. Choose a pair from /v1/fx/currencies.')
    error = None
    with _lock:
        with engine.begin() as conn:
            advisory(conn,'mfapis_fx_'+provider_symbol)
            now = int(clock())
            record = conn.execute(select(quotes).where(quotes.c.symbol == provider_symbol)).mappings().first()
            if record and 0 <= now-record['fetched_at'] < s.cache_seconds:
                return response(record,symbol,now,True,s)
            cool = conn.execute(select(failures).where(failures.c.symbol == provider_symbol)).mappings().first()
            if cool and cool['retry_at'] > now:
                raise FXError(cool['status'],cool['code'],cool['message'],cool['retry_at']-now)
            try:
                record = fetch(engine,provider_symbol,s,clock=clock)
                save(conn,quotes,{'symbol':provider_symbol},{k:v for k,v in record.items() if k!='symbol'})
            except FXError as exc:
                error = exc
        # Persist the raw response before classifying quote age; never cache a false "now".
        if error:
            cooldown(engine,provider_symbol,error,int(clock()))
            raise error
    return response(record,symbol,int(clock()),False,s)

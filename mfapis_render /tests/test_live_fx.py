"""Synthetic protocol fixtures below are tests only; never served as market data."""
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mfapis import fx, refresh
from mfapis.api import app, _clients
from mfapis.db import connect, load, observations
from mfapis.connectors import row

NOW=1793232000
SETTINGS=fx.Settings('TEST_KEY_NOT_REAL',('EUR/USD','USD/INR'),60,300,8,800)


@pytest.fixture
def db(tmp_path):
    engine=connect('sqlite:///'+str(tmp_path/'fx.db'))
    yield engine
    engine.dispose()


def payload(symbol='USD/INR', rate='83.12345678901', timestamp=NOW):
    return json.dumps({'symbol':symbol,'rate':rate,'timestamp':timestamp}).encode()


def fixture_fetch(engine,symbol,settings,clock):
    return fx.parse_quote(payload(symbol=symbol),symbol,int(clock()))


def test_latest_precision_and_inverse_share_cache(db):
    calls=[]
    def fetch(*args,**kwargs):
        calls.append(args[1]); return fixture_fetch(*args,**kwargs)
    first=fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=fetch)
    second=fx.latest(db,'INR/USD',SETTINGS,clock=lambda:NOW+10,fetch=fetch)
    assert first['rate']=='83.12345678901' and not first['cached']
    assert second['cached'] and second['inverse'] and second['timestamp']==NOW
    assert abs(Decimal(second['rate'])*Decimal(first['rate'])-1)<Decimal('1e-26')
    assert calls==['USD/INR']
    with db.connect() as conn:
        record=conn.execute(select(fx.quotes)).mappings().one()
        assert record['raw_response']==payload()
        assert record['raw_sha256']==hashlib.sha256(payload()).hexdigest()


def test_cache_expiry_and_restart(db):
    fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=fixture_fetch)
    fresh_engine=connect(db.url,initialize=False)
    try:
        r=fx.latest(fresh_engine,'USD/INR',SETTINGS,clock=lambda:NOW+59,fetch=lambda *a,**k:pytest.fail('cache miss'))
        assert r['cached']
        calls=[]
        def changed(*args,**kwargs):
            calls.append(1);return fx.parse_quote(payload(rate='84',timestamp=NOW+60),'USD/INR',NOW+60)
        r=fx.latest(fresh_engine,'USD/INR',SETTINGS,clock=lambda:NOW+60,fetch=changed)
        assert r['rate']=='84' and not r['cached'] and calls==[1]
    finally:fresh_engine.dispose()


def test_concurrent_calls_fetch_once(db):
    calls=[]
    def fetch(*args,**kwargs): calls.append(1);return fixture_fetch(*args,**kwargs)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _:fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=fetch),range(5)))
    assert calls==[1] and sum(not x['cached'] for x in results)==1


def test_stale_quotes_are_never_successful(db):
    def stale(engine,symbol,settings,clock):return fx.parse_quote(payload(timestamp=NOW-301),symbol,NOW)
    for attempt in range(2):
        with pytest.raises(fx.FXError) as error:
            fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=stale)
        assert error.value.code=='stale_quote'
    with db.connect() as conn:
        assert conn.execute(select(fx.quotes.c.provider_timestamp)).scalar()==NOW-301


@pytest.mark.parametrize('rate', ['NaN','Infinity','-1','0','1e100','text'])
def test_invalid_rates_rejected(rate):
    with pytest.raises(fx.FXError) as err:fx.parse_quote(payload(rate=rate),'USD/INR',NOW)
    assert err.value.code=='invalid_provider_response'


@pytest.mark.parametrize('stamp', [True,'1793232000',0,NOW+31,None])
def test_invalid_timestamps(stamp):
    with pytest.raises(fx.FXError):fx.parse_quote(payload(timestamp=stamp),'USD/INR',NOW)


def test_symbol_mismatch_and_malformed_json():
    for raw in [payload(symbol='EUR/USD'),b'{',b'[]',b'null']:
        with pytest.raises(fx.FXError):fx.parse_quote(raw,'USD/INR',NOW)


@pytest.mark.parametrize('code,expected', [(429,'provider_rate_limited'),(401,'provider_authentication'),(403,'provider_authentication'),(400,'pair_unavailable'),(404,'pair_unavailable'),(500,'provider_error')])
def test_http_200_provider_errors(code,expected):
    with pytest.raises(fx.FXError) as e:
        fx.parse_quote(json.dumps({'status':'error','code':code,'message':'SECRET'}).encode(),'USD/INR',NOW)
    assert e.value.code==expected and 'SECRET' not in str(e.value)


def test_credentials_missing_and_unsupported_pairs(db):
    for settings,symbol,code in [(replace(SETTINGS,key=''),'USD/INR','provider_not_configured'),(SETTINGS,'ZZZ/INR','unsupported_pair')]:
        with pytest.raises(fx.FXError) as e:fx.latest(db,symbol,settings)
        assert e.value.code==code


def test_durable_budget_limits_and_window_reset(db):
    s=replace(SETTINGS,minute_limit=2,day_limit=3)
    fx.reserve_credit(db,s,NOW);fx.reserve_credit(db,s,NOW)
    with pytest.raises(fx.FXError) as e:fx.reserve_credit(db,s,NOW)
    assert e.value.status==429
    fx.reserve_credit(db,s,NOW+60)
    with pytest.raises(fx.FXError):fx.reserve_credit(db,s,NOW+120)
    fx.reserve_credit(db,s,NOW+86400)


class Session:
    def __init__(self,items):self.items=list(items);self.calls=[]
    def get(self,*args,**kwargs):
        self.calls.append((args,kwargs)); item=self.items.pop(0)
        if isinstance(item,Exception):raise item
        return item


def http_response(status=200,body=None):
    r=requests.Response();r.status_code=status;r._content=body if body is not None else payload();return r


def test_retries_credit_accounting_and_secret_not_in_url(db,capsys):
    session=Session([requests.Timeout('TEST_KEY_NOT_REAL'),http_response()])
    sleeps=[]
    r=fx.fetch_quote(db,'USD/INR',SETTINGS,clock=lambda:NOW,sleep=sleeps.append,session=session)
    assert r['rate']=='83.12345678901' and len(sleeps)==1
    assert all('apikey' not in kwargs['params'] for _,kwargs in session.calls)
    assert session.calls[0][1]['headers']['Authorization']=='apikey TEST_KEY_NOT_REAL'
    assert 'TEST_KEY_NOT_REAL' not in capsys.readouterr().out
    with db.connect() as c:assert c.execute(select(fx.budget.c.used).where(fx.budget.c.id=='minute')).scalar()==2


def test_http429_no_retry_and_global_cooldown(db):
    session=Session([http_response(429)])
    def fetch(*args,**kwargs):return fx.fetch_quote(*args,**kwargs,session=session)
    with pytest.raises(fx.FXError) as e:fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=fetch)
    assert e.value.code=='provider_rate_limited' and len(session.calls)==1
    with pytest.raises(fx.FXError):fx.reserve_credit(db,SETTINGS,NOW+1)


def test_failed_refresh_does_not_fall_back_to_expired_cache(db):
    fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW,fetch=fixture_fetch)
    def failure(*a,**k):raise fx.FXError(502,'provider_unavailable','Unavailable',30)
    with pytest.raises(fx.FXError) as e:fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW+61,fetch=failure)
    assert e.value.code=='provider_unavailable'
    with pytest.raises(fx.FXError):fx.latest(db,'USD/INR',SETTINGS,clock=lambda:NOW+62,fetch=lambda *a,**k:pytest.fail('cooldown missed'))


def test_api_latest_historical_validation_and_key_privacy(db,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',str(db.url));monkeypatch.setenv('TWELVE_DATA_API_KEY','PRIVATE_TEST_KEY')
    _clients.clear()
    def latest(engine,symbol):return fx.response(fixture_fetch(db,'USD/INR',SETTINGS,clock=lambda:NOW),symbol,NOW,False,SETTINGS)
    monkeypatch.setattr(fx,'latest',latest)
    with TestClient(app) as client:
        caps=client.get('/v1/fx/currencies');assert caps.json()['configured'] and 'PRIVATE_TEST_KEY' not in caps.text
        r=client.get('/v1/fx/convert',params={'base':'USD','quote':'INR','amount':'100'})
        assert r.status_code==200 and r.json()['converted_amount']=='8312.34567890100'
        assert r.json()['timestamp']==NOW and r.headers['Cache-Control']=='no-store'
        assert client.get('/v1/exchange-rate?symbol=USD/INR').json()['symbol']=='USD/INR'
        assert client.get('/v1/exchange-rate?symbol=USD/INR,EUR/USD').status_code==422
        for amount in ['-1','NaN','Infinity','1000000000001']:
            assert client.get('/v1/fx/convert',params={'base':'USD','quote':'INR','amount':amount}).status_code==422
        r=client.get('/v1/fx/convert?base=USD&quote=INR&amount=100&on=2025-12-31')
        assert r.status_code==404 # Separate historical route, never substituted by latest.


def test_api_missing_key_errors_are_actionable(db,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',str(db.url));monkeypatch.delenv('TWELVE_DATA_API_KEY',raising=False);_clients.clear()
    with TestClient(app) as client:
        r=client.get('/v1/exchange-rate?symbol=USD/INR')
        assert r.status_code==503 and r.json()['error']['code']=='provider_not_configured'
        assert r.json()['request_id']==r.headers['X-Request-ID']


def test_request_limit(db,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',str(db.url));_clients.clear()
    with TestClient(app) as c:
        for _ in range(60):c.get('/v1/exchange-rate?symbol=BAD')
        assert c.get('/v1/exchange-rate?symbol=BAD').status_code==429
    _clients.clear()


def test_refresh_success_due_failure_preserves_data(db,monkeypatch):
    class Fake:
        def __init__(self,*a):self.session=type('Session',(),{'close':lambda self:None})()
    record=row('ecb','EUR/USD','reference_rate','2025-01-02','1.2','USD_per_EUR','daily',{'url':'https://example.test','sha256':'a'*64,'fetched_at':'2025-01-02T16:00:00Z'})
    monkeypatch.setattr(refresh,'extract',lambda *a:[record])
    assert refresh.refresh_source(db,'ecb',fetcher_factory=Fake)=='ok'
    assert refresh.refresh_source(db,'ecb',fetcher_factory=Fake)=='not_due'
    def failure(*a):raise ValueError('source down')
    monkeypatch.setattr(refresh,'extract',failure)
    assert refresh.refresh_source(db,'ecb',force=True,fetcher_factory=Fake)=='error'
    with db.connect() as c:
        assert c.execute(select(func.count()).select_from(observations)).scalar()==1
        state=c.execute(select(refresh.status)).mappings().one()
        assert state['status']=='error' and state['last_success_at'] is not None

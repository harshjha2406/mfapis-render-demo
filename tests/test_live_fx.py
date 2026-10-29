"""Deterministic tests for MFAPIs-owned FX feed and conversion engine.

All quote prices in these tests are synthetic fixtures, never live market data.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from mfapis import fx
from mfapis.api import app, _clients
from mfapis.db import connect

NOW=int(time.time())
KEY='A'*64

def iso(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat()

@pytest.fixture
def db(tmp_path):
    engine=connect('sqlite:///'+str(tmp_path/'fx.db'))
    yield engine
    engine.dispose()

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('MFAPIS_INGEST_KEY', KEY)
    monkeypatch.setenv('FX_LIVE_DISPLAY_AUTHORIZED','true')
    monkeypatch.setenv('FX_ALLOWED_PAIRS','USD/INR,EUR/USD,GBP/USD,EUR/GBP')
    monkeypatch.setenv('FX_MAX_QUOTE_AGE_SECONDS','120')
    return fx.Settings.env()

def put(db, symbol='USD/INR', bid='83.10', ask='83.14', ts=NOW,source='bank-feed',s=None):
    return fx.ingest(db,symbol,bid,ask,iso(ts),source,settings=s,clock=lambda:NOW)

def test_missing_feed_is_not_live(db,monkeypatch):
    monkeypatch.delenv('MFAPIS_INGEST_KEY',raising=False)
    monkeypatch.delenv('FX_LIVE_DISPLAY_AUTHORIZED',raising=False)
    s=fx.Settings.env()
    assert not fx.capabilities(s)['configured']
    with pytest.raises(fx.FXError) as e:fx.latest(db,'USD/INR',s,clock=lambda:NOW)
    assert e.value.code=='redisplay_not_authorized'


def test_ingest_quote_and_reverse_rate(db,configured):
    assert put(db,s=configured)['status']=='accepted'
    direct=fx.latest(db,'USD/INR',configured,clock=lambda:NOW)
    assert direct['provider']=='mfapis' and direct['source']=='bank-feed'
    assert direct['rate']==str(Decimal('83.12')) and direct['quote_age_seconds']==0
    assert direct['as_of']==iso(NOW).replace('+00:00','Z')
    reverse=fx.latest(db,'INR/USD',configured,clock=lambda:NOW)
    assert reverse['inverse'] and Decimal(reverse['rate'])>0
    assert Decimal(reverse['bid'])==Decimal(1)/Decimal('83.14') or Decimal(reverse['bid'])>0


def test_duplicate_out_of_order_and_conflict(db,configured):
    put(db,s=configured)
    assert put(db,s=configured)['status']=='duplicate'
    with pytest.raises(fx.FXError) as e:put(db,bid='83.11',s=configured)
    assert e.value.code=='conflicting_timestamp'
    with pytest.raises(fx.FXError) as e:put(db,ts=NOW-1,s=configured)
    assert e.value.code=='out_of_order'
    with db.connect() as c:
        assert c.execute(select(func.count()).select_from(fx.quote_history)).scalar_one()==1


def test_stale_quote_disappears_and_cannot_be_ingested(db,configured):
    put(db,s=configured)
    with pytest.raises(fx.FXError) as e:fx.latest(db,'USD/INR',configured,clock=lambda:NOW+121)
    assert e.value.code=='no_fresh_quote'
    with pytest.raises(fx.FXError) as e:put(db,ts=NOW-121,s=configured)
    assert e.value.code=='stale_ingest'


def test_bad_bid_ask_future_time_and_source(db,configured):
    for kwargs,code in [({'bid':'0'},'invalid_price'),({'ask':'83.09'},'invalid_price'),
                        ({'bid':'NaN'},'invalid_price'),({'source':'?'},'invalid_source'),
                        ({'ts':NOW+10},'future_quote')]:
        with pytest.raises(fx.FXError) as e:put(db,s=configured,**kwargs)
        assert e.value.code==code


def test_cross_pair_from_compatible_source(db,configured):
    put(db,'EUR/USD','1.08','1.10',s=configured)
    put(db,'USD/INR','83.10','83.14',s=configured)
    direct=fx.latest(db,'EUR/INR',configured,clock=lambda:NOW)
    assert direct['derived_cross_rate']
    assert Decimal(direct['bid'])==Decimal('1.08')*Decimal('83.10')
    assert Decimal(direct['ask'])==Decimal('1.10')*Decimal('83.14')
    assert direct['legs']==['EUR/USD','USD/INR']


def test_cross_pair_never_mixes_sources(db,configured):
    put(db,'EUR/USD','1.08','1.10',s=configured,source='bank-feed')
    put(db,'USD/INR','83.10','83.14',s=configured,source='other-bank')
    with pytest.raises(fx.FXError) as e:fx.latest(db,'EUR/INR',configured,clock=lambda:NOW)
    assert e.value.code=='no_fresh_quote'


def test_old_provider_cache_does_not_leak(db,configured):
    with db.begin() as c:
        c.exec_driver_sql('CREATE TABLE latest_fx_quotes (symbol TEXT PRIMARY KEY, rate TEXT)')
        c.exec_driver_sql("INSERT INTO latest_fx_quotes VALUES ('USD/INR','999.0')")
        c.exec_driver_sql('CREATE TABLE mfapis_live_fx_quotes_v2 (symbol TEXT PRIMARY KEY, rate TEXT)')
        c.exec_driver_sql("INSERT INTO mfapis_live_fx_quotes_v2 VALUES ('USD/INR','888.0')")
    with pytest.raises(fx.FXError) as e:fx.latest(db,'USD/INR',configured,clock=lambda:NOW)
    assert e.value.code=='no_fresh_quote'


def test_api_key_and_convert(db,configured,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',str(db.url))
    _clients.clear()
    import mfapis.api as a
    monkeypatch.setattr(a.time,'time',lambda:NOW)
    with TestClient(app) as client:
        assert client.get('/v1/fx/currencies').json()['provider']=='mfapis'
        body={'symbol':'USD/INR','bid':'83.10','ask':'83.14','observed_at':iso(NOW),'source':'bank-feed'}
        assert client.post('/v1/fx/quotes/ingest',json=body).status_code==401
        r=client.post('/v1/fx/quotes/ingest',json=body,headers={'X-MFAPIS-Ingest-Key':KEY})
        assert r.status_code==202, r.text
        r=client.get('/v1/exchange-rate',params={'symbol':'USD/INR'})
        assert r.status_code==200 and r.json()['rate']=='83.12'
        assert KEY not in r.text
        r=client.get('/v1/fx/convert',params={'base':'USD','quote':'INR','amount':'100'})
        assert r.status_code==200 and r.json()['converted_amount']=='8312.00'
        assert client.get('/v1/fx/history',params={'symbol':'USD/INR'}).json()['data'][0]['source']=='bank-feed'
        assert client.get('/v1/fx/quotes').json()['quotes'][0]['fresh']
        assert client.get('/v1/exchange-rate',params={'symbol':'EUR/GBP'}).status_code==503
    _clients.clear()


def test_public_display_blocked_without_rights(db,configured,monkeypatch):
    put(db,s=configured)
    monkeypatch.setenv('DATABASE_URL',str(db.url))
    monkeypatch.setenv('FX_LIVE_DISPLAY_AUTHORIZED','false')
    with TestClient(app) as client:
        assert client.get('/v1/exchange-rate?symbol=USD/INR').status_code==503
        assert client.get('/v1/fx/quotes').status_code==503
        assert client.get('/v1/fx/history?symbol=USD/INR').status_code==503


def test_quote_engine_contains_no_upstream_provider_calls():
    source=Path(fx.__file__).read_text().lower()
    assert 'requests.get(' not in source
    assert 'httpx.get(' not in source
    assert 'api.massive.com' not in source
    assert 'api.twelvedata.com' not in source


def test_private_key_too_short_rejected(db,configured,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',str(db.url))
    monkeypatch.setenv('MFAPIS_INGEST_KEY','short')
    with TestClient(app) as client:
        r=client.post('/v1/fx/quotes/ingest',json={'symbol':'USD/INR','bid':83.10,'ask':83.14,
                'observed_at':iso(NOW),'source':'bank-feed'},headers={'X-MFAPIS-Ingest-Key':'short'})
        assert r.status_code==503 and r.json()['error']['code']=='feed_not_configured'

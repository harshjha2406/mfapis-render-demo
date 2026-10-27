import json
from pathlib import Path
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mfapis.api import app
from mfapis.bootstrap import ROOT, seed, verified_records
from mfapis.db import connect, database_url, observations, revisions, watermarks


@pytest.mark.parametrize('prefix', ['postgres://', 'postgresql://', 'postgresql+psycopg://'])
def test_render_url_keeps_encoded_password(prefix):
    url = database_url(prefix + 'example:p%40ss%3Aword@db.internal:5432/demo?sslmode=require')
    assert url.drivername == 'postgresql+psycopg'
    assert url.password == 'p@ss:word'
    assert url.query['sslmode'] == 'require'


@pytest.fixture(scope='module')
def seeded_db(tmp_path_factory):
    folder = tmp_path_factory.mktemp('dashboard')
    url = 'sqlite:///' + str(folder / 'demo.db')
    engine = connect(url)
    assert seed(engine) == 21823
    yield engine, url
    engine.dispose()


def test_seed_is_idempotent_and_preserves_revisions(seeded_db):
    engine, _ = seeded_db
    assert seed(engine) == 0
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(observations)).scalar_one() == 21823
        assert conn.execute(select(func.count()).select_from(revisions)).scalar_one() == 21823
        assert conn.execute(select(func.count()).select_from(watermarks)).scalar_one() == 3


def test_corrupt_seed_rolls_back(tmp_path):
    (tmp_path / 'exports').mkdir()
    (tmp_path / 'exports/observations.jsonl').write_text('tampered')
    (tmp_path / 'seed_manifest.json').write_bytes((ROOT / 'seed_manifest.json').read_bytes())
    db = connect('sqlite://')
    with pytest.raises(ValueError, match='checksum'):
        seed(db, tmp_path)
    with db.connect() as conn:
        for table in [observations, revisions, watermarks]:
            assert conn.execute(select(func.count()).select_from(table)).scalar_one() == 0
    db.dispose()


def test_dashboard_real_data_and_catalogue(seeded_db, monkeypatch):
    _, url = seeded_db
    monkeypatch.setenv('DATABASE_URL', url)
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert 'Real data. Clear context.' in client.get('/').text
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/healthz').json() == {'status': 'ok'}
        catalogue = client.get('/v1/catalogue').json()['datasets']
        assert {d['source']: d['count'] for d in catalogue} == {'ecb':15330, 'treasury':6487, 'worldbank':6}
        for source, entity, metric in [('worldbank','IND','NY.GDP.MKTP.KD.ZG'),
                                       ('ecb','EUR/USD','reference_rate'),
                                       ('treasury','US_TREASURY','par_yield_10Y')]:
            response = client.get('/v1/observations', params={'source':source, 'entity':entity, 'metric':metric, 'limit':1000})
            assert response.status_code == 200
            assert len(response.json()['data']) >= 2
            assert response.json()['next_offset'] is None
        fx = client.get('/v1/fx/convert', params={'base':'USD','quote':'INR','amount':100,'on':'2025-12-31'})
        assert fx.status_code == 200
        assert Decimal(fx.json()['converted_amount']).quantize(Decimal('.01')) == Decimal('8986.94')
        assert client.get('/v1/fx/convert', params={'base':'USD','quote':'INR','amount':100,'on':'2025-12-28'}).status_code == 404
        assert client.get('/v1/observations', params={'source':'ecb','limit':1001}).status_code == 422


def test_empty_database_is_not_ready(tmp_path, monkeypatch):
    url = 'sqlite:///' + str(tmp_path / 'empty.db')
    connect(url).dispose()
    monkeypatch.setenv('DATABASE_URL', url)
    with TestClient(app) as client:
        assert client.get('/healthz').status_code == 503


def test_database_failure_does_not_expose_details(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path / 'missing-parent' / 'missing.db'))
    with TestClient(app) as client:
        response = client.get('/v1/catalogue')
        assert response.status_code == 503
        assert response.json()['detail'] == 'Database temporarily unavailable. Please try again shortly.'
        assert str(tmp_path) not in response.text


def test_missing_configuration_returns_unavailable(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with TestClient(app) as client:
        assert client.get('/healthz').status_code == 503
        assert client.get('/').status_code == 200

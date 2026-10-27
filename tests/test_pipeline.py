import json
import os
from datetime import date
from decimal import Decimal

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from mfapis.connectors import ecb_rows, extract, row, treasury_rows, worldbank_page
from mfapis.db import connect, load, observations, revisions, watermark, watermarks
from mfapis.http import Fetcher, safe_url

META = {"url": "https://example.com/source", "sha256": "a" * 64, "fetched_at": "2026-10-26T00:00:00+00:00"}


def observation(value="1.2"):
    return row("ecb", "EUR/USD", "reference_rate", "2025-01-02", value, "USD_per_EUR", "daily", META)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "nonsense", "0", "-2"])
def test_invalid_fx(value):
    with pytest.raises(ValueError):
        observation(value)


def test_missing_is_not_zero():
    assert observation(None)["value"] is None
    assert observation(None)["quality"] == "missing"
    assert row("treasury", "US", "yield", "2025-01-02", "0", "percent", "daily", META)["value"] == 0


def test_xml_fx_direction():
    rows = ecb_rows(b'<Envelope><Cube><Cube time="2025-01-02"><Cube currency="USD" rate="1.2"/></Cube></Cube></Envelope>', META)
    assert rows[0]["entity"] == "EUR/USD"
    assert rows[0]["unit"] == "USD_per_EUR"
    assert rows[0]["value"] == Decimal("1.2")


def test_treasury_null_and_tenors():
    xml = b'<feed xmlns:d="urn:d" xmlns:m="urn:m"><m:properties><d:NEW_DATE>2025-01-02T00:00:00</d:NEW_DATE><d:BC_1MONTH>4.12</d:BC_1MONTH><d:BC_10YEAR m:null="true"/><d:BC_30YEARDISPLAY>4.8</d:BC_30YEARDISPLAY></m:properties></feed>'
    rows = treasury_rows(xml, META)
    assert [r["metric"] for r in rows] == ["par_yield_1M", "par_yield_10Y"]
    assert rows[1]["value"] is None


def test_worldbank_pagination_and_null():
    class Fake:
        def __init__(self): self.calls = []
        def get(self, source, url, params):
            self.calls.append(params["page"])
            body = [{"page": params["page"], "pages": 2}, [{"countryiso3code": "IND",
                "indicator": {"id": "NY.GDP.MKTP.KD.ZG"}, "date": str(2020 + params["page"]), "value": None}]]
            return json.dumps(body).encode(), META
    f = Fake()
    rows = list(extract("worldbank", f, date(2021, 1, 1), date(2022, 12, 31)))
    assert f.calls == [1, 2]
    assert len(rows) == 2 and rows[0]["value"] is None


def test_api_error_not_data():
    with pytest.raises(ValueError):
        worldbank_page(b'[{"message":[{"id":"120","value":"Invalid"}]}]', META)
    with pytest.raises(ValueError):
        ecb_rows(b'<html>Blocked</html>', META)


def test_annual_query_excludes_incomplete_year():
    class Fake:
        def get(self, source, url, params):
            assert params["date"] == "2024:2024"
            body = [{"page":1,"pages":1}, [{"countryiso3code":"IND",
                "indicator":{"id":"NY.GDP.MKTP.KD.ZG"},"date":"2024","value":6.5}]]
            return json.dumps(body).encode(), META
    rows = list(extract("worldbank", Fake(), date(2024,1,1), date(2025,6,1)))
    assert len(rows) == 1 and rows[0]["observation_date"] == date(2024,12,31)


def verify_database(engine):
    r = observation()
    load(engine, "ecb", [r, r], date(2025, 1, 2))
    load(engine, "ecb", [r], date(2025, 1, 2))
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(observations)).scalar() == 1
        assert conn.execute(select(func.count()).select_from(revisions)).scalar() == 1
    changed = observation("1.3")
    load(engine, "ecb", [changed], date(2025, 1, 1))
    with engine.connect() as conn:
        assert conn.execute(select(observations.c.value)).scalar() == Decimal("1.3")
        assert conn.execute(select(func.count()).select_from(revisions)).scalar() == 2
    assert watermark(engine, "ecb") == date(2025, 1, 2)
    with pytest.raises(ValueError):
        load(engine, "ecb", [r, changed], date(2025, 1, 3))
    assert watermark(engine, "ecb") == date(2025, 1, 2)


def test_sqlite_idempotency_revisions_and_checkpoint():
    verify_database(connect("sqlite://"))


def test_transaction_rolls_back():
    db = connect("sqlite://")
    bad = observation()
    bad["entity"] = "EUR/GBP"
    bad["frequency"] = None
    with pytest.raises(Exception):
        load(db, "ecb", [observation(), bad], date(2025, 1, 2))
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(observations)).scalar() == 0
        assert conn.execute(select(func.count()).select_from(revisions)).scalar() == 0
    assert watermark(db, "ecb") is None


def test_empty_does_not_advance():
    db = connect("sqlite://")
    with pytest.raises(ValueError):
        load(db, "ecb", [], date(2025, 1, 2))
    assert watermark(db, "ecb") is None


def test_postgres_schema_compiles():
    ddl = str(CreateTable(observations).compile(dialect=postgresql.dialect()))
    assert "NUMERIC(30, 12)" in ddl and "PRIMARY KEY" in ddl


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires a separate disposable PostgreSQL test database")
def test_postgres_integration():
    db = connect(os.environ["TEST_DATABASE_URL"])
    assert db.dialect.name == "postgresql"
    # Only run against a dedicated EMPTY test database. Never deletes existing data.
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(observations)).scalar() == 0
    verify_database(db)


def response(status, content=b"hello", retry_after=None):
    r = requests.Response()
    r.status_code, r._content, r.url = status, content, "https://example.com/data"
    if retry_after: r.headers["Retry-After"] = retry_after
    return r


def test_retry_preserves_error_and_success(tmp_path):
    class Session:
        headers = {}
        def __init__(self): self.responses = [response(429, b"limit", "0"), response(200, b"data")]
        def get(self, *a, **k): return self.responses.pop(0)
    pauses = []
    body, meta = Fetcher(tmp_path, Session(), pauses.append).get("test", "https://example.com/data")
    assert body == b"data" and pauses == [0]
    events = [json.loads(x) for x in (tmp_path / "http_evidence.jsonl").read_text().splitlines()]
    assert [x["status"] for x in events] == [429, 200]
    assert all((tmp_path / x["raw_path"]).exists() for x in events)


def test_403_no_retry(tmp_path):
    class Session:
        headers = {}
        def get(self, *a, **k): return response(403)
    with pytest.raises(requests.HTTPError):
        Fetcher(tmp_path, Session(), lambda _: pytest.fail("Must not retry 403")).get("test", "https://example.com/data")


def test_secret_redaction():
    assert "secret" not in safe_url("https://example.com/?api_key=secret&page=1")


def test_api_cross_rate_and_exact_date(tmp_path, monkeypatch):
    from mfapis.api import app
    url = "sqlite:///" + str(tmp_path / "api.db")
    db = connect(url)
    gbp = row("ecb", "EUR/GBP", "reference_rate", "2025-01-02", ".8", "GBP_per_EUR", "daily", META)
    load(db, "ecb", [observation(), gbp], date(2025, 1, 2))
    monkeypatch.setenv("DATABASE_URL", url)
    with TestClient(app) as client:
        r = client.get("/v1/fx/convert", params={"base":"USD", "quote":"GBP", "amount":"3", "on":"2025-01-02"})
        assert r.status_code == 200
        assert Decimal(r.json()["converted_amount"]) == Decimal(2)
        assert client.get("/v1/fx/convert", params={"base":"USD", "quote":"GBP", "amount":"3", "on":"2025-01-04"}).status_code == 404
        page = client.get("/v1/observations", params={"source":"ecb", "limit":1}).json()
        assert len(page["data"]) == 1 and page["next_offset"] == 1

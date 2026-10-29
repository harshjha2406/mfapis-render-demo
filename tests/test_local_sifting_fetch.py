"""Offline tests for the private dashboard's on-demand SiftingIO refresh."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mfapis.api import app
from mfapis import local_sifting_refresh as live


def fake_request(host="127.0.0.1:8014", origin="http://127.0.0.1:8014",
                 peer="127.0.0.1", action="refresh"):
    return SimpleNamespace(client=SimpleNamespace(host=peer),
        headers={"host": host, "origin": origin, "x-mfapis-local-action": action})


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MFAPIS_LOCAL_SIFTING_REFRESH", raising=False)
    with pytest.raises(HTTPException) as error:
        live.validate_local_request(fake_request())
    assert error.value.status_code == 404


def test_api_rejects_remote_and_missing_origin(monkeypatch):
    monkeypatch.setenv("MFAPIS_LOCAL_SIFTING_REFRESH", "true")
    for params in [{"peer":"203.0.113.10"},{"origin":"https://evil.example"},
                   {"origin":""},{"action":""},{"host":"public.example:8014"}]:
        with pytest.raises(HTTPException) as error:
            live.validate_local_request(fake_request(**params))
        assert error.value.status_code == 403
    live.validate_local_request(fake_request())


def test_disabled_route_does_not_call_provider(monkeypatch):
    monkeypatch.delenv("MFAPIS_LOCAL_SIFTING_REFRESH", raising=False)
    with TestClient(app) as client:
        r=client.post("/v1/local/sifting/refresh",
            headers={"Origin":"http://127.0.0.1:8014","X-MFAPIS-Local-Action":"refresh"})
        assert r.status_code == 404


def test_manual_refresh_uses_mocked_provider_and_no_secret_in_output(monkeypatch):
    monkeypatch.setenv("SIFTING_API_KEY", "not-for-browser")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////private/test.db")
    monkeypatch.setenv("SIFTING_PAIRS", "EUR/USD,GBP/USD")
    monkeypatch.setattr(live, "_LAST_ATTEMPT", None)
    # The initial request must work even on a newly started CI runner.
    monkeypatch.setattr(live.time, "monotonic", lambda: 10.0)
    class Db:
        def dispose(self): pass
    monkeypatch.setattr(live, "connect", lambda url, initialize=False: Db())
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(live.requests, "Session", Session)
    monkeypatch.setattr(live.sifting_fx_worker, "fetch_quote",
        lambda session,pair,key:{"symbol":pair,"bid":"1.11","ask":"1.12",
                                 "observed_at":"2026-10-29T17:00:00Z","source":"siftingio_reference"})
    calls=[]
    def fake_ingest(db,symbol,bid,ask,observed_at,source):
        calls.append(symbol)
        return {"status":"accepted"}
    monkeypatch.setattr(live.fx,"ingest",fake_ingest,raising=False)
    result=live.fetch_and_store()
    assert result["updated"] == 2 and result["requested"] == 2 and calls == ["EUR/USD","GBP/USD"]
    assert "not-for-browser" not in str(result)


def test_manual_refresh_has_cooldown(monkeypatch):
    monkeypatch.setattr(live, "_LAST_ATTEMPT", live.time.monotonic())
    with pytest.raises(HTTPException) as error:
        live.fetch_and_store()
    assert error.value.status_code == 429


def test_static_dashboard_has_separate_fetch_button():
    root=Path(__file__).resolve().parents[1] / "mfapis/static"
    html=(root / "forex.html").read_text()
    js=(root / "forex.js").read_text()
    assert 'id="fetch-latest"' in html
    assert 'id="refresh"' in html
    assert "'/v1/local/sifting/refresh'" in js
    assert "X-MFAPIS-Local-Action" in js
    assert "SIFTING_API_KEY" not in js

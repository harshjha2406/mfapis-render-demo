"""Forex UI tests: local assets only, synthetic/unauthenticated requests."""
from pathlib import Path

from fastapi.testclient import TestClient
from mfapis.api import app

STATIC = Path(__file__).resolve().parents[1] / "mfapis" / "static"


def test_dashboard_route_loads_without_database_or_provider_key(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SIFTING_API_KEY", raising=False)
    with TestClient(app) as client:
        response = client.get("/forex")
        assert response.status_code == 200
        assert "Currency converter" in response.text
        assert "Live quote board" in response.text
        assert '<script src="/assets/forex.js" defer>' in response.text


def test_dashboard_assets_are_served():
    with TestClient(app) as client:
        assert client.get("/assets/forex.css").status_code == 200
        assert client.get("/assets/forex.js").status_code == 200
        assert client.get("/assets/forex.js").headers["content-type"].startswith(("text/javascript", "application/javascript"))


def test_dashboard_uses_only_local_apis_not_upstream_provider():
    html = (STATIC / "forex.html").read_text()
    js = (STATIC / "forex.js").read_text()
    for value in ["SIFTING_API_KEY", "MFAPIS_INGEST_KEY", "api.sifting.io", "biquote.io", "https://"]:
        assert value not in js
    assert "api('/v1/fx/quotes')" in js
    assert "api('/v1/fx/currencies')" in js
    assert "'/v1/fx/convert?'" in js
    assert "local MFAPIs database only" in html


def test_dashboard_shows_stale_not_fresh_when_old():
    js = (STATIC / "forex.js").read_text()
    assert "ageOf(r) <= state.maxAge" in js
    assert "r.fresh !== false" in js
    assert "Stale" in js
    assert "No fresh conversion" in js


def test_existing_explorer_not_replaced():
    with TestClient(app) as client:
        existing = client.get("/")
        assert existing.status_code == 200
        assert "Real data. Clear context." in existing.text
        assert client.get("/docs").status_code == 200

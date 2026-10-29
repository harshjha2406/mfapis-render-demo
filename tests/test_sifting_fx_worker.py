"""Offline tests only: synthetic fixtures, no SiftingIO calls or secrets."""
from datetime import datetime, timezone
import json

import pytest

from scripts import sifting_fx_worker as adapter

NOW = 1780000000.0
QUOTED_MS = int(NOW * 1000) - 2000


def sample(**changes):
    data = {"s": "EURUSD", "b": "1.16925", "a": "1.16943", "t": QUOTED_MS, "B": "150000", "A": "130000"}
    data.update(changes)
    return data


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code, self.data = status, sample() if data is None else data
    def json(self):
        return self.data


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.requests = []
    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.response
    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return FakeResponse(202, {"status": "accepted"})


def test_parse_realistic_response():
    q = adapter.parse_quote(sample(), "EUR/USD", now=NOW)
    assert q["symbol"] == "EUR/USD"
    assert q["bid"] == "1.16925"
    assert q["ask"] == "1.16943"
    assert q["source"] == "siftingio_reference"
    assert q["observed_at"].endswith("Z")


@pytest.mark.parametrize("changes", [
    {"s": "GBPUSD"}, {"b": "nan"}, {"b": "0"}, {"b": "1.19", "a": "1.17"},
    {"t": 1780000000}, {"t": QUOTED_MS-200000}, {"t": int((NOW+10)*1000)},
    {"t": True}, {"a": "Infinity"},
])
def test_rejects_invalid_or_stale_quote(changes):
    with pytest.raises(adapter.QuoteError):
        adapter.parse_quote(sample(**changes), "EUR/USD", now=NOW)


def test_source_key_is_only_sent_to_sifting():
    sess = FakeSession()
    q = adapter.fetch_quote(sess, "EUR/USD", "local-secret", now=NOW)
    assert q["source"] == "siftingio_reference"
    method, url, kwargs = sess.requests[0]
    assert method == "GET" and url.endswith("/forex/EURUSD")
    assert "local-secret" not in url
    assert kwargs["headers"]["X-API-Key"] == "local-secret"


@pytest.mark.parametrize("status", [401, 403, 404, 429, 503, 500])
def test_http_errors_do_not_expose_response_or_secret(status):
    sess = FakeSession(FakeResponse(status, {"error": "sensitive-secret"}))
    with pytest.raises(adapter.QuoteError) as exc:
        adapter.fetch_quote(sess, "EUR/USD", "secret-key", now=NOW)
    assert "secret-key" not in str(exc.value)
    assert "sensitive-secret" not in str(exc.value)


@pytest.mark.parametrize("url", [
    "https://production.example.com", "https://api.sifting.io", "http://localhost.evil:8012",
    "http://127.0.0.1:8012/path", "http://127.0.0.1:8012?key=secret",
    "http://name:password@127.0.0.1:8012", "http://127.0.0.1:80@evil.org:8012",
])
def test_ingestion_url_must_be_loopback(url):
    with pytest.raises(adapter.QuoteError):
        adapter.checked_local_url(url)


def test_ingest_posts_only_to_local_api():
    sess = FakeSession()
    payload = adapter.parse_quote(sample(), "EUR/USD", now=NOW)
    status = adapter.ingest_quote(sess, payload, base_url="http://127.0.0.1:8012", ingest_key="x"*40)
    assert status == "accepted"
    assert sess.requests[0][1] == "http://127.0.0.1:8012/v1/fx/quotes/ingest"
    assert sess.requests[0][2]["json"] == payload
    assert "X-API-Key" not in sess.requests[0][2]["headers"]


def test_one_shot_preview_no_ingestion(monkeypatch, capsys):
    sess = FakeSession()
    monkeypatch.setenv("SIFTING_API_KEY", "some-secret")
    monkeypatch.setenv("SIFTING_PAIRS", "EUR/USD")
    assert adapter.run(session=sess, now=NOW) == 0
    assert len(sess.requests) == 1
    assert sess.requests[0][0] == "GET"
    out = capsys.readouterr().out
    assert "some-secret" not in out
    assert "Valid quote snapshots: 1/1" in out


def test_unauthorized_halts_before_next_pair(monkeypatch):
    monkeypatch.setenv("SIFTING_API_KEY", "some-secret")
    monkeypatch.setenv("SIFTING_PAIRS", "EUR/USD,GBP/USD")
    sess = FakeSession(FakeResponse(401))
    assert adapter.run(session=sess, now=NOW) == 1
    assert len(sess.requests) == 1


def test_max_five_pairs_and_no_duplicates(monkeypatch):
    for raw in ["EUR/USD,EUR/USD", "AAA/AAA", "USDEUR", "EUR/USD,GBP/USD,USD/JPY,USD/CHF,AUD/USD,CAD/USD"]:
        monkeypatch.setenv("SIFTING_PAIRS", raw)
        with pytest.raises(adapter.QuoteError):
            adapter.pairs_from_env()

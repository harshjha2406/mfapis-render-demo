"""Deterministic freshness monitoring tests; synthetic local quotes only."""
import time
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from mfapis import fx
from mfapis.db import connect, database_url
from scripts import check_fx_health as health


def temporary_quotes(tmp_path, now, *, pairs=health.PAIRS, overrides=None):
    url = "sqlite:///" + str(tmp_path / "health.db")
    engine = connect(url)
    overrides = overrides or {}
    with engine.begin() as connection:
        for pair in pairs:
            values = {
                "symbol": pair,
                "bid": "1.1000",
                "ask": "1.1002",
                "observed_at": now - 7,
                "received_at": now - 3,
                "source": "synthetic-test",
                "raw_sha256": "a" * 64,
            }
            values.update(overrides.get(pair, {}))
            connection.execute(fx.latest_quotes.insert().values(**values))
    engine.dispose()
    return url


def test_all_pairs_fresh_on_sqlite(tmp_path):
    now = 2_000_000_000
    url = temporary_quotes(tmp_path, now)
    result = health.inspect_quotes(url, now=now)
    assert [r["status"] for r in result] == ["FRESH"] * 5


def test_stale_missing_and_future(tmp_path):
    now = 2_000_000_000
    pairs = health.PAIRS[:4]
    url = temporary_quotes(tmp_path, now, pairs=pairs, overrides={
        "EUR/USD": {"observed_at": now - 130, "received_at": now - 120},
        "GBP/USD": {"observed_at": now + 1, "received_at": now + 2},
    })
    result = health.inspect_quotes(url, now=now)
    assert [r["status"] for r in result] == [
        "STALE", "FUTURE", "FRESH", "FRESH", "MISSING"
    ]


def test_bad_price_and_timestamp(tmp_path):
    now = 2_000_000_000
    url = temporary_quotes(tmp_path, now, pairs=health.PAIRS[:2], overrides={
        "EUR/USD": {"bid": "2.0", "ask": "1.0"},
        "GBP/USD": {"received_at": now - 30},
    })
    result = health.inspect_quotes(url, now=now)
    assert result[0]["status"] == "BAD_PRICE"
    assert result[1]["status"] == "BAD_TIMESTAMP"


def test_no_sqlite_file_created(tmp_path):
    path = tmp_path / "not-created.db"
    with pytest.raises(health.HealthCheckError, match="not found"):
        health.inspect_quotes("sqlite:///" + str(path))
    assert not path.exists()


def test_missing_quote_table_is_not_created(tmp_path):
    url = "sqlite:///" + str(tmp_path / "empty.db")
    sqlite3.connect(str(tmp_path / "empty.db")).close()
    with pytest.raises(health.HealthCheckError, match="quote table unavailable"):
        health.inspect_quotes(url)
    engine = connect(url, initialize=False)
    with engine.connect() as c:
        names = c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars().all()
    engine.dispose()
    assert "mfapis_owned_fx_latest_v1" not in names


def test_postgres_url_normalization_no_external_connection():
    url = database_url("postgresql://user:p%40ss@postgres.internal/demo")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss"


def test_does_not_reveal_db_credentials(monkeypatch, capsys):
    def failed_connection(url, initialize=False):
        raise ValueError("postgresql://user:PRIVATE-PASSWORD@host/database")

    monkeypatch.setattr(health, "connect", failed_connection)
    with pytest.raises(health.HealthCheckError) as exc:
        health.inspect_quotes("postgresql://user:PRIVATE-PASSWORD@host/database")
    assert "PRIVATE-PASSWORD" not in str(exc.value)


def test_main_respects_database_url_and_threshold(tmp_path, monkeypatch, capsys):
    now = int(time.time())
    url = temporary_quotes(tmp_path, now)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("FX_MAX_QUOTE_AGE_SECONDS", "120")
    assert health.main() == 0
    output = capsys.readouterr().out
    assert "Healthy pairs: 5 / 5" in output
    assert "OVERALL HEALTH: PASS" in output

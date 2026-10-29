"""Read-only MFAPIs Forex freshness checks for SQLite or PostgreSQL.

DATABASE_URL selects the database. If unset, use the existing local demo SQLite file.
No API feed fetching, ingestion, schema creation, or public quote display occurs here.
"""
import os
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Allow direct execution using: python scripts/check_fx_health.py
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from mfapis import fx
from mfapis.db import connect, database_url

LOCAL_DB = Path.home() / "Desktop/mfapis-local-data/fx_demo.sqlite3"
PAIRS = ("EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD")
MAX_AGE_SECONDS = 120


class HealthCheckError(Exception):
    pass


def configured_url():
    return os.getenv("DATABASE_URL") or "sqlite:///" + str(LOCAL_DB)


def inspect_quotes(url, *, pairs=PAIRS, now=None, max_age=MAX_AGE_SECONDS):
    """Return per-symbol status using SELECT queries only (no schema changes)."""
    if not 5 <= max_age <= 86400:
        raise HealthCheckError("Invalid freshness threshold")
    now = time.time() if now is None else float(now)

    # SQLite normally creates a missing file on connection. Avoid doing that.
    try:
        parsed = database_url(url)
        if parsed.get_backend_name() == "sqlite":
            database = parsed.database
            if database and database != ":memory:" and not Path(database).is_file():
                raise HealthCheckError("Local SQLite database not found")
    except HealthCheckError:
        raise
    except (ValueError, TypeError, SQLAlchemyError):
        raise HealthCheckError("Invalid database configuration") from None

    engine = None
    try:
        engine = connect(url, initialize=False)
        stmt = select(
            fx.latest_quotes.c.symbol,
            fx.latest_quotes.c.bid,
            fx.latest_quotes.c.ask,
            fx.latest_quotes.c.observed_at,
            fx.latest_quotes.c.received_at,
        ).where(fx.latest_quotes.c.symbol.in_(pairs))
        with engine.connect() as connection:
            records = connection.execute(stmt).mappings().all()
    except (SQLAlchemyError, OSError, ValueError):
        # The exception may contain a PostgreSQL URL or credentials. Never print it.
        raise HealthCheckError("Database query failed or quote table unavailable") from None
    finally:
        if engine is not None:
            engine.dispose()

    by_pair = {record["symbol"]: record for record in records}
    results = []

    for pair in pairs:
        record = by_pair.get(pair)
        if record is None:
            results.append({"symbol": pair, "status": "MISSING"})
            continue

        try:
            observed = int(record["observed_at"])
            received = int(record["received_at"])
            age = now - observed
            lag = received - observed
            bid = Decimal(str(record["bid"]))
            ask = Decimal(str(record["ask"]))
            valid_price = (bid.is_finite() and ask.is_finite()
                           and Decimal(0) < bid <= ask)
            valid_time = (0 <= lag and received <= now + 5)
            if not valid_price:
                status = "BAD_PRICE"
            elif not valid_time:
                status = "BAD_TIMESTAMP"
            elif age < 0:
                status = "FUTURE"
            elif age > max_age:
                status = "STALE"
            else:
                status = "FRESH"
        except (TypeError, ValueError, InvalidOperation, OverflowError):
            status, age, lag = "BAD_DATA", None, None

        results.append({
            "symbol": pair,
            "status": status,
            "age": age,
            "lag": lag,
        })

    return results


def main():
    try:
        max_age = int(os.getenv("FX_MAX_QUOTE_AGE_SECONDS", str(MAX_AGE_SECONDS)))
        results = inspect_quotes(configured_url(), max_age=max_age)
    except (HealthCheckError, ValueError) as error:
        # HealthCheckError strings are deliberately safe for logs.
        message = str(error) if isinstance(error, HealthCheckError) else "Invalid FX_MAX_QUOTE_AGE_SECONDS"
        print("HEALTH CHECK ERROR:", message)
        return 1

    healthy = sum(row["status"] == "FRESH" for row in results)
    print("\n========== MFAPIs FX HEALTH CHECK ==========")
    for row in results:
        if row["status"] == "MISSING":
            print(row["symbol"], "| MISSING")
        else:
            age = row.get("age")
            lag = row.get("lag")
            print(
                row["symbol"], "|", row["status"],
                "| Age:", round(age, 1) if age is not None else "unknown", "seconds",
                "| Ingestion lag:", lag if lag is not None else "unknown", "seconds",
            )
    print("\nHealthy pairs:", healthy, "/", len(results))
    print("OVERALL HEALTH:", "PASS" if healthy == len(results) else "FAIL")
    return 0 if healthy == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

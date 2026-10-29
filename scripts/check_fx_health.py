import sqlite3
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

DB = Path.home() / "Desktop/mfapis-local-data/fx_demo.sqlite3"

PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
]

MAX_AGE_SECONDS = 120

if not DB.exists():
    print("ERROR: Local database not found.")
    sys.exit(1)

try:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT symbol, bid, ask, observed_at, received_at
            FROM mfapis_owned_fx_latest_v1
        """).fetchall()
except sqlite3.Error as error:
    print("DATABASE ERROR:", error)
    sys.exit(1)

latest = {row["symbol"]: row for row in rows}
now = time.time()
healthy = 0

print("\n========== MFAPIs FX HEALTH CHECK ==========")

for pair in PAIRS:
    row = latest.get(pair)

    if row is None:
        print(pair, "| MISSING")
        continue

    age = now - int(row["observed_at"])
    received = int(row["received_at"])
    lag = received - int(row["observed_at"])

    status = "FRESH" if 0 <= age <= MAX_AGE_SECONDS else "STALE"

    print(
        pair,
        "|", status,
        "| Age:", round(age, 1), "seconds",
        "| Ingestion lag:", lag, "seconds",
        "| Bid:", row["bid"],
        "| Ask:", row["ask"]
    )

    if status == "FRESH":
        healthy += 1

print("\nHealthy pairs:", healthy, "/", len(PAIRS))

if healthy == len(PAIRS):
    print("OVERALL HEALTH: PASS")
    sys.exit(0)
else:
    print("OVERALL HEALTH: FAIL")
    sys.exit(1)

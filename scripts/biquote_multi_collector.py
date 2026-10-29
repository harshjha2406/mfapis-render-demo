import os
import time
import math
import secrets
from pathlib import Path
from datetime import datetime, timezone

import requests

# Use only the local test database
os.environ["DATABASE_URL"] = (
    "sqlite:///" +
    str(Path.home() / "Desktop/mfapis-local-data/fx_demo.sqlite3")
)

# Temporary authentication for local testing
os.environ["MFAPIS_INGEST_KEY"] = secrets.token_hex(32)

# Never enable public display without permission
os.environ["FX_LIVE_DISPLAY_AUTHORIZED"] = "false"
os.environ["AUTO_REFRESH_HISTORY"] = "false"

from fastapi.testclient import TestClient
from mfapis.api import app

PAIRS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "AUDUSD": "AUD/USD",
}

with requests.Session() as session, TestClient(app) as client:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"GET"},
        respect_retry_after_header=True
    )

    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry)
    )

    for cycle in range(1, 4):
        print(f"\n========== CYCLE {cycle}/3 ==========",
              flush=True)

        for provider_symbol, mfapis_symbol in PAIRS.items():
            try:
                response = session.get(
                    f"https://biquote.io/api/{provider_symbol}",
                    params={"allowStale": "false"},
                    timeout=15
                )
                response.raise_for_status()
                quote = response.json()

                bid = float(quote["bid"])
                ask = float(quote["ask"])
                timestamp = quote["timestamp"]

                observed = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )

                age = (
                    datetime.now(timezone.utc) - observed
                ).total_seconds()

                midpoint = (bid + ask) / 2
                spread_pct = (
                    ((ask - bid) / midpoint) * 100
                    if midpoint > 0 else float("inf")
                )

                valid = (
                    0 <= age <= 120
                    and math.isfinite(bid)
                    and math.isfinite(ask)
                    and 0 < bid <= ask
                    and spread_pct <= 0.5
                    and quote.get("stale") is False
                    and quote.get("marketState") == "open"
                )

                if not valid:
                    print(mfapis_symbol, "REJECTED: invalid or stale")
                    continue

                result = client.post(
                    "/v1/fx/quotes/ingest",
                    json={
                        "symbol": mfapis_symbol,
                        "bid": bid,
                        "ask": ask,
                        "observed_at": timestamp,
                        "source": "biquote_MT5_Broker1"
                    },
                    headers={
                        "X-MFAPIS-Ingest-Key":
                            os.environ["MFAPIS_INGEST_KEY"]
                    }
                )

                print(
                    mfapis_symbol,
                    "| Bid:", bid,
                    "| Ask:", ask,
                    "| Age:", round(age, 1),
                    "| MFAPIs HTTP:", result.status_code
                )

                if result.status_code != 202:
                    print("Details:", result.text[:300])

            except Exception as error:
                print(mfapis_symbol, "ERROR:", str(error))

        if cycle < 3:
            time.sleep(15)

print("\nMulti-currency collection test completed.")

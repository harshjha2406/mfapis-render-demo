import os
import time
import math
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PAIRS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "AUDUSD": "AUD/USD",
}

API_URL = "http://127.0.0.1:8002"
KEY = os.getenv("MFAPIS_INGEST_KEY", "")

if len(KEY) < 32:
    raise SystemExit("Missing local MFAPIS_INGEST_KEY")

def validate(q):
    if not isinstance(q, dict):
        raise ValueError("Invalid quote response")

    bid = float(q["bid"])
    ask = float(q["ask"])

    observed = datetime.fromisoformat(
        q["timestamp"].replace("Z", "+00:00")
    )

    if observed.tzinfo is None:
        raise ValueError("Timestamp has no timezone")

    age = (
        datetime.now(timezone.utc) - observed
    ).total_seconds()

    midpoint = (bid + ask) / 2

    spread_pct = (
        (ask - bid) / midpoint * 100
        if midpoint > 0 else float("inf")
    )

    if not (
        0 <= age <= 120
        and math.isfinite(bid)
        and math.isfinite(ask)
        and 0 < bid <= ask
        and spread_pct <= 0.5
        and q.get("stale") is False
        and q.get("marketState") == "open"
    ):
        raise ValueError("Stale or invalid quote")

    return bid, ask, age

retry = Retry(
    total=2,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods={"GET"},
    respect_retry_after_header=True,
)

with requests.Session() as provider, requests.Session() as mfapis:
    provider.mount(
        "https://",
        HTTPAdapter(max_retries=retry)
    )

    for cycle in range(1, 3):
        print(f"\n========== HTTP CYCLE {cycle}/2 ==========",
              flush=True)

        try:
            response = provider.get(
                "https://biquote.io/api/latest",
                params=[
                    ("symbols", symbol)
                    for symbol in PAIRS
                ],
                timeout=15
            )
            response.raise_for_status()
            quotes = response.json()

            if not isinstance(quotes, dict):
                raise ValueError("Unexpected batch response")

            for symbol, mfapis_symbol in PAIRS.items():
                try:
                    q = quotes.get(symbol)

                    if q is None:
                        raise ValueError("Quote missing")

                    bid, ask, age = validate(q)

                    result = mfapis.post(
                        API_URL + "/v1/fx/quotes/ingest",
                        json={
                            "symbol": mfapis_symbol,
                            "bid": bid,
                            "ask": ask,
                            "observed_at": q["timestamp"],
                            "source": "biquote_MT5_Broker1"
                        },
                        headers={
                            "X-MFAPIS-Ingest-Key": KEY
                        },
                        timeout=10
                    )

                    print(
                        mfapis_symbol,
                        "| Age:", round(age, 1),
                        "| HTTP:", result.status_code,
                        "|", result.json().get("status", "")
                    )

                    if result.status_code != 202:
                        print("Error:", result.text[:200])

                except Exception as error:
                    print(mfapis_symbol, "ERROR:", error)

        except Exception as error:
            print("Batch fetch failed:", error)

        if cycle < 2:
            time.sleep(15)

print("\nStandalone HTTP worker test completed.")

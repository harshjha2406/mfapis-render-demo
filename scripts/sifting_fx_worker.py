"""SiftingIO REST quote adapter for the private MFAPIs development demo.

Uses SiftingIO's /v1/last/quote/forex/{PAIR} snapshots, with no credentials in URLs.
Default mode previews current prices and never writes to a database or external server.
--ingest posts only to a loopback MFAPIs API which must already be running.

The adapter cannot create prices and will not mark stale or invalid quotes current.
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import requests

API_ORIGIN = "https://api.sifting.io"
SOURCE = "siftingio_reference"
DEFAULT_PAIRS = ("EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD")
PAIR_RE = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")
KEY_FILE = Path.home() / ".config" / "mfapis" / "sifting_api_key"
INGEST_KEY_FILE = Path.home() / ".config" / "mfapis" / "local_ingest_key"


class QuoteError(Exception):
    """Safe-to-display error with no request headers or API keys."""


def read_key(environment_name, file_path):
    value = os.environ.get(environment_name, "").strip()
    if not value and file_path.is_file():
        value = file_path.read_text(encoding="utf-8").strip()
    if not value:
        raise QuoteError(f"Missing {environment_name}. Configure it privately first.")
    return value


def pairs_from_env():
    raw = os.getenv("SIFTING_PAIRS", ",".join(DEFAULT_PAIRS))
    pairs = [v.strip().upper() for v in raw.split(",")]
    if not pairs or len(pairs) > 5 or any(not PAIR_RE.fullmatch(p) or p[:3] == p[4:] for p in pairs):
        raise QuoteError("SIFTING_PAIRS must contain 1-5 comma-separated currency pairs, e.g. EUR/USD,GBP/USD")
    if len(set(pairs)) != len(pairs):
        raise QuoteError("SIFTING_PAIRS contains duplicates")
    return pairs


def parse_quote(data, pair, *, now=None, max_age=120):
    """Validate SiftingIO's short-key schema and return MFAPIs ingestion payload."""
    if not isinstance(data, dict):
        raise QuoteError("Unexpected quote payload")
    symbol = pair.replace("/", "")
    if data.get("s") != symbol:
        raise QuoteError("Response symbol does not match requested pair")
    if isinstance(data.get("t"), bool) or not isinstance(data.get("t"), int):
        raise QuoteError("Invalid quote timestamp")
    try:
        bid = Decimal(str(data["b"]))
        ask = Decimal(str(data["a"]))
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise QuoteError("Invalid quote prices") from None
    if not (bid.is_finite() and ask.is_finite() and 0 < bid <= ask <= Decimal("1000000000000")):
        raise QuoteError("Invalid bid/ask values")
    if len(str(bid)) > 80 or len(str(ask)) > 80:
        raise QuoteError("Price precision exceeds limits")
    observed_ms = data["t"]
    # A genuine current millisecond epoch must be at least year 2001.
    if observed_ms < 978307200000:
        raise QuoteError("Timestamp must be Unix milliseconds")
    now = time.time() if now is None else float(now)
    age = now - (observed_ms / 1000)
    if age < -5 or age > max_age:
        raise QuoteError("Quote is stale or has a future timestamp")
    # Ingestion accepts a timestamp no more than 5s in the future.
    observed = datetime.fromtimestamp(observed_ms / 1000, tz=timezone.utc)
    return {
        "symbol": pair,
        "bid": str(bid),
        "ask": str(ask),
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "source": SOURCE,
    }


def checked_local_url(value):
    """Do not accidentally send demo quote payloads or ingestion keys to a public host."""
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
            or not parts.port or parts.username or parts.password or parts.path or parts.query or parts.fragment):
        raise QuoteError("MFAPIS_API_URL must be http://127.0.0.1:PORT (loopback only)")
    return value


def fetch_quote(session, pair, api_key, *, now=None):
    symbol = pair.replace("/", "")
    try:
        response = session.get(
            f"{API_ORIGIN}/v1/last/quote/forex/{symbol}",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=12,
        )
    except requests.RequestException:
        raise QuoteError("SiftingIO request failed (network error)") from None
    if response.status_code != 200:
        status = response.status_code
        if status == 401:
            raise QuoteError("SiftingIO rejected the API key (401)")
        if status == 403:
            raise QuoteError("SiftingIO Forex access not enabled for this key (403)")
        if status == 404:
            raise QuoteError(f"SiftingIO has no current data for {pair} (404)")
        if status == 429:
            raise QuoteError("SiftingIO quota or rate limit reached (429); stop and check usage")
        if status == 503:
            raise QuoteError("SiftingIO current snapshot unavailable/stale (503)")
        raise QuoteError(f"SiftingIO HTTP {status}")
    try:
        raw = response.json()
    except ValueError:
        raise QuoteError("SiftingIO returned non-JSON data") from None
    return parse_quote(raw, pair, now=now)


def ingest_quote(session, payload, *, base_url, ingest_key):
    base_url = checked_local_url(base_url)
    if len(ingest_key) < 32:
        raise QuoteError("Local MFAPIS_INGEST_KEY must be at least 32 characters")
    try:
        response = session.post(
            base_url + "/v1/fx/quotes/ingest",
            json=payload,
            headers={"X-MFAPIS-Ingest-Key": ingest_key},
            timeout=10,
        )
    except requests.RequestException:
        raise QuoteError("Local MFAPIs ingestion server is not reachable") from None
    if response.status_code != 202:
        raise QuoteError(f"Local ingestion failed (HTTP {response.status_code})")
    try:
        result = response.json()
    except ValueError:
        raise QuoteError("Local ingestion returned unexpected data") from None
    if result.get("status") not in {"accepted", "duplicate"}:
        raise QuoteError("Local ingestion returned unexpected status")
    return result["status"]


def run(*, ingest=False, session=None, now=None):
    key = read_key("SIFTING_API_KEY", KEY_FILE)
    pairs = pairs_from_env()
    local_url = None
    ingest_key = None
    if ingest:
        local_url = checked_local_url(os.getenv("MFAPIS_API_URL", "http://127.0.0.1:8012"))
        ingest_key = read_key("MFAPIS_INGEST_KEY", INGEST_KEY_FILE)
        if len(ingest_key) < 32:
            raise QuoteError("Local ingestion key is too short")
    own_session = session is None
    if own_session:
        session = requests.Session()
    success = 0
    try:
        for pair in pairs:
            try:
                quote = fetch_quote(session, pair, key, now=now)
                state = "preview"
                if ingest:
                    state = ingest_quote(session, quote, base_url=local_url, ingest_key=ingest_key)
                print(f'{pair}: bid={quote["bid"]} ask={quote["ask"]} | {state} | {quote["observed_at"]}', flush=True)
                success += 1
            except QuoteError as error:
                print(f"{pair}: {error}", flush=True)
                if "(429)" in str(error) or "(401)" in str(error) or "(403)" in str(error):
                    break  # Quota or authentication failure affects all pairs.
        print(f"Valid quote snapshots: {success}/{len(pairs)}", flush=True)
        return 0 if success > 0 else 1
    finally:
        if own_session:
            session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private SiftingIO -> MFAPIs Forex demo")
    parser.add_argument("--ingest", action="store_true", help="Post only to a local MFAPIs service")
    args = parser.parse_args(argv)
    try:
        return run(ingest=args.ingest)
    except (QuoteError, OSError) as error:
        print(f"SiftingIO setup error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Explicit, loopback-only SiftingIO refresh for the personal Forex dashboard.

Never enabled on Render; no scheduled upstream requests or API keys in browser code.
"""
import os
import threading
import time
from pathlib import Path

import requests
from fastapi import HTTPException

from scripts import sifting_fx_worker
from . import fx
from .db import connect

_LOCK = threading.Lock()
_LAST_ATTEMPT = None
COOLDOWN_SECONDS = 180


def validate_local_request(request):
    """Require the local demo switch, loopback peer, matching origin, and custom header."""
    if os.getenv("MFAPIS_LOCAL_SIFTING_REFRESH", "false").lower() != "true":
        raise HTTPException(404, "This local-only feature is disabled")
    port = os.getenv("MFAPIS_LOCAL_DASHBOARD_PORT", "8014")
    allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    peer = request.client.host if request.client else ""
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    header = request.headers.get("x-mfapis-local-action", "")
    if (peer not in {"127.0.0.1", "::1"}
            or origin not in allowed
            or host not in {f"127.0.0.1:{port}", f"localhost:{port}"}
            or header != "refresh"):
        raise HTTPException(403, "Local dashboard request required")


def fetch_and_store():
    """Retrieve up to five authorized snapshots and insert them in the local database."""
    global _LAST_ATTEMPT
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(429, "Refresh already running")
    try:
        now = time.monotonic()
        if _LAST_ATTEMPT is not None:
            remaining = COOLDOWN_SECONDS - (now - _LAST_ATTEMPT)
            if remaining > 0:
                raise HTTPException(429, f"Please wait {int(remaining) + 1}s before another provider refresh")
        _LAST_ATTEMPT = now
        try:
            key = sifting_fx_worker.read_key("SIFTING_API_KEY", sifting_fx_worker.KEY_FILE)
            pairs = sifting_fx_worker.pairs_from_env()
            database_url = os.getenv("DATABASE_URL", "")
            if not database_url.startswith("sqlite:"):
                raise ValueError("A local SQLite demo database is required")
            db = connect(database_url, initialize=False)
        except (OSError, ValueError, sifting_fx_worker.QuoteError):
            raise HTTPException(503, "Local demo key or SQLite database is not configured") from None

        updated = 0
        problems = []
        try:
            with requests.Session() as session:
                for pair in pairs:
                    try:
                        quote = sifting_fx_worker.fetch_quote(session, pair, key)
                        result = fx.ingest(db, quote["symbol"], quote["bid"], quote["ask"],
                                           quote["observed_at"], quote["source"])
                        if result["status"] in {"accepted", "duplicate"}:
                            updated += 1
                    except sifting_fx_worker.QuoteError as error:
                        problems.append(f"{pair}: {error}")
                        if any(code in str(error) for code in ("(401)", "(403)", "(429)")):
                            break
                    except fx.FXError as error:
                        problems.append(f"{pair}: {error.code}")
                    except Exception:
                        problems.append(f"{pair}: data storage unavailable")
        finally:
            db.dispose()
        return {"updated": updated, "requested": len(pairs), "errors": problems,
                "message": ("Quotes received" if updated else "No current quotes received")}
    finally:
        _LOCK.release()

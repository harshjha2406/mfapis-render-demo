"""Optional server-side SiftingIO FX collector for the single-process demo.

The upstream key stays in Render environment variables and is never sent to a browser.
This worker only ingests validated observations into MFAPIs; public display remains
controlled separately by FX_LIVE_DISPLAY_AUTHORIZED. Do not enable more than one
worker process when using a single-connection SiftingIO subscription.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote as url_quote

from sqlalchemy.exc import SQLAlchemyError

from . import fx
from .db import connect, database_url

logger = logging.getLogger("uvicorn.error")
SYMBOLS = ("EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD")
WS_HOST = "wss://stream.sifting.io/ws/v1"


def configured():
    return os.getenv("SIFTING_WS_ENABLED", "false").strip().lower() == "true"


def settings():
    """Return safe validated configuration without reading secrets into logs."""
    if not configured():
        return None
    key = os.getenv("SIFTING_API_KEY", "").strip()
    database = os.getenv("DATABASE_URL", "")
    if not key or not database:
        logger.error("FX stream configuration incomplete")
        return None
    try:
        parsed = database_url(database)
        if parsed.get_backend_name() != "postgresql":
            logger.error("Hosted FX stream requires PostgreSQL")
            return None
        seconds = int(os.getenv("SIFTING_MIN_WRITE_SECONDS", "30"))
    except (ValueError, TypeError):
        logger.error("Invalid FX stream configuration")
        return None
    if not (15 <= seconds <= 3600):
        logger.error("Invalid FX stream write interval")
        return None
    return key, database, seconds


def validate_tick(message, now=None):
    """Validate the market symbol, bid/ask and millisecond observation timestamp."""
    if not isinstance(message, dict) or message.get("f") != "tick" or message.get("class") != "fx":
        return None
    raw_symbol = message.get("s")
    mapping = {p.replace("/", ""): p for p in SYMBOLS}
    if not isinstance(raw_symbol, str) or raw_symbol not in mapping:
        return None
    millisecond = message.get("t")
    if isinstance(millisecond, bool) or not isinstance(millisecond, int) or millisecond < 978307200000:
        return None
    now = time.time() if now is None else now
    age = now - millisecond / 1000
    if not (-5 <= age <= 120):
        return None
    try:
        bid = Decimal(str(message["b"]))
        ask = Decimal(str(message["a"]))
        if not (bid.is_finite() and ask.is_finite() and Decimal(0) < bid <= ask <= Decimal("1000000000000")):
            return None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if len(str(bid)) > 80 or len(str(ask)) > 80:
        return None
    timestamp = datetime.fromtimestamp(millisecond / 1000, timezone.utc)
    return mapping[raw_symbol], str(bid), str(ask), timestamp


def handle_tick(message, engine, last_writes, *, now=None, monotonic=None, write_gap=30):
    """Persist at most one valid price per pair per time interval; never print prices."""
    now = time.time() if now is None else now
    monotonic = time.monotonic() if monotonic is None else monotonic
    tick = validate_tick(message, now=now)
    if tick is None:
        return False
    symbol, bid, ask, observed = tick
    previous = last_writes.get(symbol)
    if previous is not None and monotonic - previous < write_gap:
        return False
    try:
        result = fx.ingest(engine, symbol, bid, ask, observed, "siftingio_reference")
    except (fx.FXError, SQLAlchemyError, OSError):
        return False
    if result.get("status") not in {"accepted", "duplicate"}:
        return False
    last_writes[symbol] = monotonic
    return True


def _open_connection(key):
    # SiftingIO's WebSocket requires a URL key. Never log the URL or exceptions
    # that may reproduce it. Only the server process sees this credential.
    import websocket
    uri = WS_HOST + "?key=" + url_quote(key, safe="")
    return websocket.create_connection(uri, timeout=12)


def receive_session(stop, key, database, write_gap, *, socket_factory=_open_connection):
    import websocket
    socket = None
    engine = None
    writes = {}
    count = 0
    try:
        engine = connect(database, initialize=False)
        socket = socket_factory(key)
        socket.send(json.dumps({"op": "subscribe", "product": "fx", "symbols": [p.replace("/", "") for p in SYMBOLS]}))
        last_ping = time.monotonic()
        logger.info("FX stream subscribed to five pairs")
        while not stop.is_set():
            if time.monotonic() - last_ping >= 45:
                socket.send('{"op":"ping"}')
                last_ping = time.monotonic()
            try:
                frame = socket.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not frame:
                break
            try:
                message = json.loads(frame)
            except (ValueError, TypeError):
                continue
            if not isinstance(message, dict):
                continue
            if message.get("f") == "error":
                logger.warning("FX stream reported an error frame")
                if message.get("code") in {"auth_failed", "max_connections", "auth_required"}:
                    return False
            elif handle_tick(message, engine, writes, write_gap=write_gap):
                count += 1
                if count == 1 or count % 20 == 0:
                    logger.info("FX stream accepted %d validated quote events", count)
        return True
    finally:
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass
        if engine is not None:
            engine.dispose()


def run_forever(stop):
    config = settings()
    if config is None:
        return
    key, database, write_gap = config
    retry = 10
    logger.info("FX stream enabled for private server-side ingestion")
    while not stop.is_set():
        try:
            recoverable = receive_session(stop, key, database, write_gap)
        except Exception:
            # Do not log driver/HTTP/socket exceptions: they may contain credentials.
            logger.warning("FX stream disconnected; will retry")
            recoverable = True
        if not recoverable:
            logger.warning("FX stream stopped after authorization or connection limit error")
            return
        if stop.wait(retry):
            return
        retry = min(retry * 2, 60)


def start_worker():
    stop = threading.Event()
    if configured():
        thread = threading.Thread(target=run_forever, args=(stop,), daemon=True, name="sifting-fx-stream")
        thread.start()
    return stop

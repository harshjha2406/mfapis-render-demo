"""MFAPIs-owned FX quote ingestion, calculated conversions, and historical datasets."""
import os
import time
import threading
from contextlib import asynccontextmanager
from uuid import uuid4
import hmac
from datetime import datetime
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal, localcontext
from typing import Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Header, Request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .connectors import ATTRIBUTIONS
from . import fx, refresh
from .db import connect, json_record, observations

@asynccontextmanager
async def lifespan(app):
    from . import sifting_stream
    stop = refresh.start_worker()
    stream_stop = sifting_stream.start_worker()
    try:
        yield
    finally:
        stream_stop.set()
        stop.set()


app = FastAPI(title="MFAPIs Financial Data Explorer", version="0.5.0", lifespan=lifespan,
              description="MFAPIs-owned FX market quote intake, storage and conversion. Requires your own authenticated authorized live quote feed; no external forex rate API dependency. Historical ECB, Treasury and World Bank datasets are separate.")


@app.exception_handler(fx.FXError)
async def fx_failure(request, exc):
    return JSONResponse(status_code=exc.status,
        content={"detail":exc.message,"error":{"code":exc.code,"message":exc.message},"request_id":getattr(request.state,"request_id",None)},
        headers={"Retry-After":str(exc.retry_after)} if exc.retry_after else {})


# Basic single-process edge protection for this demonstration. The durable provider
# budget protects paid upstream usage across replicas. Commercial tenant quotas need
# authenticated keys and a shared rate limiter at the gateway.
_clients = {}
_clients_lock = threading.Lock()


@app.middleware("http")
async def request_controls(request, call_next):
    request.state.request_id=uuid4().hex
    if request.url.path in {"/v1/exchange-rate", "/v1/fx/convert"}:
        now=int(time.time()); host=request.client.host if request.client else "unknown"
        with _clients_lock:
            expired=[k for k,v in _clients.items() if v[0]!=now//60]
            for k in expired: del _clients[k]
            window,count=_clients.get(host,(now//60,0))
            if count>=60 or (host not in _clients and len(_clients)>=10000):
                return JSONResponse(status_code=429,content={"detail":"Too many requests. Retry shortly.","request_id":request.state.request_id},headers={"Retry-After":str(60-now%60)})
            _clients[host]=(window,count+1)
    result=await call_next(request)
    result.headers["X-Request-ID"]=request.state.request_id
    result.headers["X-Content-Type-Options"]="nosniff"
    result.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    if request.url.path=="/" or request.url.path.startswith("/v1/"):
        result.headers["Cache-Control"]="no-store"
    if request.url.path=="/":
        result.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return result


@app.get("/v1/fx/currencies")
def currencies():
    return fx.capabilities()


class FXQuoteIn(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z]{3}/[A-Z]{3}$", max_length=7)
    bid: Decimal
    ask: Decimal
    observed_at: datetime
    source: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")


def verify_ingest_key(key: str | None):
    secret = os.getenv("MFAPIS_INGEST_KEY", "").strip()
    if len(secret)<32:
        raise fx.FXError(503, "feed_not_configured", "Set a random MFAPIS_INGEST_KEY of at least 32 characters")
    if not key or not hmac.compare_digest(key, secret):
        raise fx.FXError(401, "unauthorized", "A valid ingestion key is required")


@app.post("/v1/fx/quotes/ingest", status_code=202)
def ingest_quote(payload: FXQuoteIn, x_mfapis_ingest_key: str | None = Header(default=None)):
    """Private collector endpoint. Feed adapters send real, authorized market quotes here."""
    verify_ingest_key(x_mfapis_ingest_key)
    db=engine()
    try:
        return fx.ingest(db, payload.symbol, payload.bid, payload.ask, payload.observed_at, payload.source)
    finally: db.dispose()


@app.get("/v1/fx/quotes")
def latest_quote_list():
    db=engine()
    try: return fx.available_quotes(db)
    finally: db.dispose()


@app.get("/v1/fx/history")
def fx_history(symbol: str=Query(pattern="^[A-Z]{3}/[A-Z]{3}$"), limit: int=Query(100,ge=1,le=1000)):
    db=engine()
    try: return fx.history(db,symbol,limit)
    finally: db.dispose()


@app.get("/v1/exchange-rate")
def exchange_rate(symbol: str = Query(pattern="^[A-Z]{3}/[A-Z]{3}$")):
    db=engine()
    try: return fx.latest(db,symbol)
    finally: db.dispose()


STATIC = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.exception_handler(SQLAlchemyError)
async def database_failure(request, exc):
    # Never send connection strings, SQL, or credentials to public clients.
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable. Please try again shortly."})


@app.post("/v1/local/sifting/refresh", include_in_schema=False)
def refresh_sifting_for_local_dashboard(request: Request):
    from .local_sifting_refresh import validate_local_request, fetch_and_store
    validate_local_request(request)
    return fetch_and_store()


@app.get("/forex", include_in_schema=False)
def forex_dashboard():
    return FileResponse(STATIC / "forex.html")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz", include_in_schema=False)
def health():
    db = engine()
    try:
        with db.connect() as conn:
            sources = set(conn.execute(select(observations.c.source).distinct()).scalars())
        if not {"ecb", "treasury", "worldbank"}.issubset(sources):
            raise HTTPException(503, "Dataset initialization incomplete")
        return {"status": "ok"}
    finally:
        db.dispose()


@app.get("/v1/catalogue")
def catalogue():
    db = engine()
    try:
        with db.connect() as conn:
            groups = conn.execute(select(observations.c.source,
                func.count().label("count"), func.min(observations.c.observation_date).label("first_date"),
                func.max(observations.c.observation_date).label("last_date"),
                func.max(observations.c.retrieved_at).label("last_retrieved_at")
                ).group_by(observations.c.source).order_by(observations.c.source)).mappings().all()
            instruments = conn.execute(select(observations.c.source, observations.c.entity,
                observations.c.metric, observations.c.unit).distinct().order_by(
                observations.c.source, observations.c.entity, observations.c.metric)).mappings().all()
            refresh_rows = conn.execute(select(refresh.status)).mappings().all()
        return {"datasets": [{**json_record(g), "attribution": ATTRIBUTIONS[g["source"]],
                "series": [dict(i) for i in instruments if i["source"] == g["source"]]} for g in groups],
                "refresh": {r["source"]:dict(r) for r in refresh_rows},
                "automatic_refresh_enabled":os.getenv("AUTO_REFRESH_HISTORY","false").lower()=="true",
                "note": "Historical source observations; daily or annual frequency. Live FX endpoints use only fresh authenticated quote observations sent to MFAPIs; no synthetic or daily-reference quotes are labeled live."}
    finally:
        db.dispose()


def engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise HTTPException(503, "Set DATABASE_URL and ingest data first")
    return connect(url, initialize=False)


@app.get("/v1/observations")
def series(source: Literal["worldbank", "ecb", "treasury"], entity: str | None = None,
           metric: str | None = None, start: date | None = None, end: date | None = None,
           limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    if start and end and start > end:
        raise HTTPException(400, "start must be <= end")
    stmt = select(observations).where(observations.c.source == source)
    for name, value in [("entity", entity), ("metric", metric)]:
        if value is not None:
            stmt = stmt.where(observations.c[name] == value)
    if start:
        stmt = stmt.where(observations.c.observation_date >= start)
    if end:
        stmt = stmt.where(observations.c.observation_date <= end)
    db = engine()
    try:
        with db.connect() as conn:
            rows = conn.execute(stmt.order_by(observations.c.observation_date, observations.c.entity,
                                observations.c.metric, observations.c.unit).offset(offset).limit(limit + 1)).mappings().all()
        return {"data": [json_record(r) for r in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None,
                "attribution": ATTRIBUTIONS[source]}
    finally:
        db.dispose()


@app.get("/v1/fx/convert")
def convert(base: str = Query(pattern="^[A-Z]{3}$"), quote: str = Query(pattern="^[A-Z]{3}$"),
            amount: Decimal = Query(ge=0,le=Decimal("1000000000000"),max_digits=24,decimal_places=12), on: date | None = None):
    if on is None:
        db=engine()
        try:
            result=fx.latest(db,base+"/"+quote)
            with localcontext() as ctx:
                ctx.prec=60
                converted=amount*Decimal(result["rate"])
            return {**result,"base":base,"quote":quote,"amount":str(amount),"converted_amount":str(converted)}
        finally: db.dispose()
    if on>date.today():
        raise HTTPException(400,"Historical observation date cannot be in the future")
    # Exact observation date, no weekend carry-forward hidden from clients.
    db = engine()
    try:
        with db.connect() as conn:
            rows = conn.execute(select(observations).where(observations.c.source == "ecb",
                        observations.c.observation_date == on)).mappings().all()
        rates = {r["entity"].split("/")[1]: r["value"] for r in rows if r["value"] is not None}
        if not rates:
            raise HTTPException(404, "No reference rates for this exact date")
        rates["EUR"] = Decimal(1)
        if base not in rates or quote not in rates:
            raise HTTPException(404, "Currency unavailable on this date")
        rate = rates[quote] / rates[base]
        return {"base": base, "quote": quote, "observation_date": str(on), "rate": str(rate),
                "amount": str(amount), "converted_amount": str(amount * rate),
                "mode":"historical", "provider":"ecb", "modified": "Cross-rate and amount calculated by MFAPIs", "attribution": ATTRIBUTIONS["ecb"]}
    finally:
        db.dispose()

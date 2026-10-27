"""Read-only historical-data dashboard and API; commercial auth is a later layer."""
import os
from datetime import date
from decimal import Decimal
from typing import Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .connectors import ATTRIBUTIONS
from .db import connect, json_record, observations

app = FastAPI(title="MFAPIs Financial Data Explorer", version="0.2.0",
              description="Real historical data from World Bank, ECB and US Treasury. Not a real-time feed.")
STATIC = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.exception_handler(SQLAlchemyError)
async def database_failure(request, exc):
    # Never send connection strings, SQL, or credentials to public clients.
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable. Please try again shortly."})


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
        return {"datasets": [{**json_record(g), "attribution": ATTRIBUTIONS[g["source"]],
                "series": [dict(i) for i in instruments if i["source"] == g["source"]]} for g in groups],
                "note": "Real historical source data. Not a real-time feed; no automatic refresh is scheduled."}
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
            on: date = Query(), amount: Decimal = Query(ge=0)):
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
                "modified": "Cross-rate and amount calculated by MFAPIs", "attribution": ATTRIBUTIONS["ecb"]}
    finally:
        db.dispose()

import hashlib
import json
from datetime import date
from decimal import Decimal

from sqlalchemy import Column, Date, Integer, MetaData, Numeric, String, Table, Text, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import make_url

metadata = MetaData()
KEY = ["source", "entity", "metric", "observation_date", "unit"]
observations = Table("observations", metadata,
    Column("source", String(40), primary_key=True),
    Column("entity", String(80), primary_key=True),
    Column("metric", String(100), primary_key=True),
    Column("observation_date", Date, primary_key=True),
    Column("unit", String(40), primary_key=True),
    Column("value", Numeric(30, 12)), Column("frequency", String(20), nullable=False),
    Column("quality", String(20), nullable=False), Column("source_url", Text, nullable=False),
    Column("raw_sha256", String(64), nullable=False), Column("retrieved_at", String(40), nullable=False),
    Column("attribution", Text, nullable=False))
revisions = Table("observation_revisions", metadata,
    Column("revision_id", String(64), primary_key=True), Column("source", String(40), nullable=False),
    Column("first_seen_at", String(40), nullable=False), Column("record_json", Text, nullable=False))
watermarks = Table("watermarks", metadata,
    Column("source", String(40), primary_key=True), Column("through_date", Date, nullable=False))


def json_record(record):
    # Decimal strings preserve numeric precision across JSON clients.
    return {k: str(v) if isinstance(v, (Decimal, date)) else v for k, v in record.items()}


def database_url(url):
    """Render supplies a plain PostgreSQL URL; select our installed psycopg 3 driver."""
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed


def connect(url, initialize=True):
    parsed = database_url(url)
    options = {"connect_timeout": 10} if parsed.drivername.startswith("postgresql") else {}
    engine = create_engine(parsed, pool_pre_ping=True, connect_args=options)
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise ValueError("Use PostgreSQL, or SQLite for local smoke tests")
    if initialize:
        metadata.create_all(engine)
    return engine


def watermark(engine, source):
    with engine.connect() as conn:
        return conn.execute(select(watermarks.c.through_date).where(watermarks.c.source == source)).scalar()


def load(engine, source, records, through):
    if not records:
        raise ValueError("Zero records; checkpoint not advanced")
    unique = {}
    for r in records:
        if r["source"] != source:
            raise ValueError("Mixed sources in transaction")
        key = tuple(r[k] for k in KEY)
        if key in unique and (r["value"], r["quality"]) != (unique[key]["value"], unique[key]["quality"]):
            raise ValueError("Conflicting duplicate source records")
        unique[key] = r
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    with engine.begin() as conn:
        # Prevent overlapping writers for one source on PostgreSQL.
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:source))"), {"source": source})
        for r in unique.values():
            content = {k: json_record(r)[k] for k in KEY + ["value", "frequency", "quality"]}
            revision_id = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            conn.execute(insert(revisions).values(revision_id=revision_id, source=source,
                first_seen_at=r["retrieved_at"], record_json=json.dumps(json_record(r))).on_conflict_do_nothing(index_elements=["revision_id"]))
            stmt = insert(observations).values(**r)
            conn.execute(stmt.on_conflict_do_update(index_elements=KEY,
                set_={c: getattr(stmt.excluded, c) for c in r if c not in KEY}))
        # Do not regress the watermark during an explicit historical backfill.
        old = conn.execute(select(watermarks.c.through_date).where(watermarks.c.source == source)).scalar()
        checkpoint = max(old, through) if old else through
        stmt = insert(watermarks).values(source=source, through_date=checkpoint)
        conn.execute(stmt.on_conflict_do_update(index_elements=["source"], set_={"through_date": checkpoint}))
    return len(unique)

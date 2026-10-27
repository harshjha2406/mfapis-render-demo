"""Seed an EMPTY database atomically from the verified real-data snapshot.

Runs at service startup. Existing observations are never reset or overwritten.
No source fetching or public write endpoint is needed to display the demonstration.
"""
import hashlib
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import func, select, text

from .connectors import row
from .db import KEY, connect, json_record, observations, revisions, watermarks
from .http import emit

ROOT = Path(__file__).resolve().parent.parent


def verified_records(root=ROOT):
    manifest = json.loads((root / "seed_manifest.json").read_text())
    snapshot = (root / "exports/observations.jsonl").read_bytes()
    if hashlib.sha256(snapshot).hexdigest() != manifest["snapshot_sha256"]:
        raise ValueError("Snapshot checksum mismatch")
    records, hashes, keys = [], set(), set()
    for line in snapshot.decode().splitlines():
        original = json.loads(line)
        r = row(original["source"], original["entity"], original["metric"],
                original["observation_date"], original["value"], original["unit"],
                original["frequency"], {"url": original["source_url"],
                "sha256": original["raw_sha256"], "fetched_at": original["retrieved_at"]})
        key = tuple(r[k] for k in KEY)
        if key in keys:
            raise ValueError("Duplicate key in startup snapshot")
        keys.add(key)
        digest = r["raw_sha256"]
        if digest not in hashes:
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Invalid source digest")
            if hashlib.sha256((root / "data/raw" / (digest + ".bin")).read_bytes()).hexdigest() != digest:
                raise ValueError("Raw source checksum mismatch")
            hashes.add(digest)
        records.append(r)
    if dict(Counter(r["source"] for r in records)) != manifest["counts"]:
        raise ValueError("Snapshot counts mismatch")
    return records


def seed(engine, root=ROOT):
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('mfapis_initial_snapshot'))"))
            for source in ["ecb", "treasury", "worldbank"]:
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:source))"), {"source": source})
        count = conn.execute(select(func.count()).select_from(observations)).scalar_one()
        if count:
            emit("seed_skipped", reason="Existing observations retained", count=count)
            return 0
        if conn.execute(select(func.count()).select_from(revisions)).scalar_one() or conn.execute(
                select(func.count()).select_from(watermarks)).scalar_one():
            raise ValueError("Refusing to seed a partially populated database")
        records = verified_records(root)
        snapshots = []
        for r in records:
            normalized = json_record(r)
            content = {k: normalized[k] for k in KEY + ["value", "frequency", "quality"]}
            snapshots.append({"revision_id": hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
                "source": r["source"], "first_seen_at": r["retrieved_at"], "record_json": json.dumps(normalized)})
        for offset in range(0, len(records), 500):
            conn.execute(observations.insert(), records[offset:offset+500])
            conn.execute(revisions.insert(), snapshots[offset:offset+500])
        for source in sorted({r["source"] for r in records}):
            conn.execute(watermarks.insert().values(source=source,
                through_date=max(r["observation_date"] for r in records if r["source"] == source)))
    emit("seed_success", count=len(records), database=engine.dialect.name, mode="archived_real_data")
    return len(records)


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL before starting the service")
    db = connect(url)
    try:
        seed(db)
    finally:
        db.dispose()


if __name__ == "__main__":
    main()

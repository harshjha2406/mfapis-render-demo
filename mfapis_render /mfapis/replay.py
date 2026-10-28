"""Rebuild the demonstration database from hash-verified real source responses."""
import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path

from .connectors import ecb_rows, treasury_rows, worldbank_page
from .db import connect, load
from .http import emit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    p.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    args = p.parse_args()
    if not args.database_url: p.error("Set DATABASE_URL")
    if args.start > args.end: p.error("Invalid date range")
    root = Path(args.data_dir)
    grouped = {}
    for line in (root / "http_evidence.jsonl").read_text().splitlines():
        meta = json.loads(line)
        if meta.get("status") != 200 or meta["source"] not in {"worldbank", "ecb", "treasury"}:
            continue
        body = (root / meta["raw_path"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != meta["sha256"]:
            raise ValueError("Raw response checksum mismatch")
        source = meta["source"]
        rows = worldbank_page(body, meta)[1] if source == "worldbank" else (
            ecb_rows(body, meta) if source == "ecb" else treasury_rows(body, meta))
        # Apply chronological captures separately so later source revisions prevail.
        grouped.setdefault(source, []).append([r for r in rows if args.start <= r["observation_date"] <= args.end])
    db = connect(args.database_url)
    for source, batches in grouped.items():
        for rows in batches:
            if rows:
                n = load(db, source, rows, max(r["observation_date"] for r in rows))
                emit("replay_success", source=source, records_upserted=n, database=db.dialect.name)


if __name__ == "__main__":
    main()

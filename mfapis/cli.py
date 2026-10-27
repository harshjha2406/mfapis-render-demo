import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from .connectors import extract
from .db import connect, json_record, load, observations, watermark
from .http import Fetcher, emit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", choices=["worldbank", "ecb", "treasury", "all"])
    p.add_argument("--start", type=date.fromisoformat, default=date(2020, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--full", action="store_true", help="Ignore watermark and reconcile requested history")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = p.parse_args()
    if not args.database_url:
        p.error("Set DATABASE_URL, or explicitly choose sqlite:///demo.db for a smoke test")
    if args.start > args.end or args.end > date.today():
        p.error("Invalid date range")
    engine = connect(args.database_url)
    fetcher = Fetcher(args.data_dir)
    failed = []
    for source in ["worldbank", "ecb", "treasury"] if args.source == "all" else [args.source]:
        try:
            start = args.start
            prior = watermark(engine, source)
            if prior and not args.full:
                # Annual indicators are revised far back; periodically use --full.
                days = 3 * 366 if source == "worldbank" else 7
                start = max(start, prior - timedelta(days=days))
            if start > args.end:
                raise ValueError("Requested history predates checkpoint; use --full")
            rows = list(extract(source, fetcher, start, args.end))
            if not rows:
                raise ValueError("No observations in requested range")
            frame = pd.DataFrame(rows)
            missing = int(frame["value"].isna().sum())
            count = load(engine, source, rows, max(r["observation_date"] for r in rows))
            with engine.connect() as conn:
                latest = conn.execute(select(observations).where(observations.c.source == source)
                    .order_by(observations.c.observation_date.desc(), observations.c.entity, observations.c.metric).limit(10)).mappings().all()
            target = Path(args.data_dir) / "samples"
            target.mkdir(exist_ok=True, parents=True)
            (target / f"{source}.json").write_text(json.dumps([json_record(r) for r in latest], indent=2))
            emit("pipeline_success", source=source, records_upserted=count, missing_values=missing,
                 range_start=str(start), range_end=str(args.end), database=engine.dialect.name)
        except Exception as exc:
            failed.append(source)
            emit("pipeline_failed", source=source, error_type=type(exc).__name__, message=str(exc)[:240])
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

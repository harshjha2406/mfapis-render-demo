"""Refresh historical datasets on startup and periodically while the process runs.

On sleeping free hosting, this is opportunistic, not a guaranteed cron schedule.
Raw HTTP response bytes and manifests are persisted in PostgreSQL, not just disk.
Run `python -m mfapis.refresh --force` from a real scheduler for a refresh SLA.
"""
import argparse
import json
import os
import tempfile
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import BigInteger, Column, LargeBinary, String, Table, Text, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .db import connect, load, metadata, watermark
from .connectors import extract
from .http import Fetcher, emit

status = Table('ingestion_status',metadata,
    Column('source',String(40),primary_key=True),Column('last_attempt_at',BigInteger),
    Column('last_success_at',BigInteger),Column('status',String(20),nullable=False),
    Column('message',Text),Column('next_attempt_at',BigInteger,nullable=False))
raw = Table('raw_source_responses',metadata,
    Column('sha256',String(64),primary_key=True),Column('source',String(40),nullable=False),
    Column('body',LargeBinary,nullable=False),Column('metadata_json',Text,nullable=False))


class DurableFetcher(Fetcher):
    def __init__(self,root,engine):
        super().__init__(root)
        self.engine=engine

    def _log(self,meta):
        super()._log(meta)
        if 'raw_path' not in meta: return
        body=(self.root/meta['raw_path']).read_bytes()
        insert=pg_insert if self.engine.dialect.name=='postgresql' else sqlite_insert
        with self.engine.begin() as conn:
            conn.execute(insert(raw).values(sha256=meta['sha256'],source=meta['source'],body=body,
                metadata_json=json.dumps(meta)).on_conflict_do_nothing(index_elements=['sha256']))


def refresh_source(db,source,force=False,fetcher_factory=DurableFetcher):
    now=int(time.time())
    # Session advisory lock spans HTTP + atomic data load. Another process skips immediately.
    with db.connect() as lease:
        locked=False
        if db.dialect.name=='postgresql':
            locked=lease.execute(text('SELECT pg_try_advisory_lock(hashtext(:name))'),{'name':'mfapis_refresh_'+source}).scalar()
            lease.commit()
            if not locked: return 'busy'
        try:
            with db.begin() as conn:
                old=conn.execute(select(status).where(status.c.source==source)).mappings().first()
                if old and old['next_attempt_at']>now and not force: return 'not_due'
                last_success=old['last_success_at'] if old else None
                values=dict(last_attempt_at=now,last_success_at=last_success,status='running',message=None,next_attempt_at=now+600)
                if old: conn.execute(status.update().where(status.c.source==source).values(**values))
                else: conn.execute(status.insert().values(source=source,**values))
            try:
                start=date(2024,1,1); prior=watermark(db,source)
                if prior and source!='worldbank': start=max(start,prior-timedelta(days=7))
                with tempfile.TemporaryDirectory(prefix='mfapis-source-') as directory:
                    fetcher=fetcher_factory(directory,db)
                    try: records=list(extract(source,fetcher,start,date.today()))
                    finally: fetcher.session.close()
                if not records: raise ValueError('No observations returned')
                count=load(db,source,records,max(r['observation_date'] for r in records))
                finished=int(time.time())
                with db.begin() as conn:
                    conn.execute(status.update().where(status.c.source==source).values(
                        status='ok',last_success_at=finished,message=f'{count} observations reconciled',next_attempt_at=finished+21600))
                emit('scheduled_refresh_success',source=source,records_upserted=count)
                return 'ok'
            except Exception as exc:
                # Store error class only; request exceptions can carry URLs/credentials.
                with db.begin() as conn:
                    conn.execute(status.update().where(status.c.source==source).values(
                        status='error',message=type(exc).__name__,next_attempt_at=int(time.time())+900))
                emit('scheduled_refresh_failed',source=source,error_type=type(exc).__name__)
                return 'error'
        finally:
            if locked:
                lease.execute(text('SELECT pg_advisory_unlock(hashtext(:name))'),{'name':'mfapis_refresh_'+source})
                lease.commit()


def run_once(force=False,stop=None):
    db=connect(os.environ['DATABASE_URL'])
    results={}
    try:
        for source in ['ecb','treasury','worldbank']:
            if stop and stop.is_set(): break
            results[source]=refresh_source(db,source,force)
    finally: db.dispose()
    return results


def worker(stop):
    while not stop.is_set():
        try: run_once(stop=stop)
        except Exception as exc: emit('refresh_worker_error',error_type=type(exc).__name__)
        stop.wait(300)  # Interruptible background wait; per-source next_attempt_at controls work.


def start_worker():
    stop=threading.Event()
    if os.getenv('AUTO_REFRESH_HISTORY','false').lower()=='true':
        threading.Thread(target=worker,args=(stop,),name='history-refresh',daemon=True).start()
    return stop


def main():
    p=argparse.ArgumentParser(); p.add_argument('--force',action='store_true'); args=p.parse_args()
    results=run_once(args.force)
    if 'error' in results.values(): raise SystemExit(1)


if __name__=='__main__': main()

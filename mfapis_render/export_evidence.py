"""Read a verified database and export counts, normalized data and PostgreSQL inserts."""
import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from mfapis.db import connect, json_record, observations, revisions

p = argparse.ArgumentParser()
p.add_argument('--database-url', required=True)
args = p.parse_args()
db = connect(args.database_url)
root = Path('exports')
root.mkdir(exist_ok=True)
with db.connect() as conn:
    records = conn.execute(select(observations).order_by(observations.c.source, observations.c.entity,
        observations.c.metric, observations.c.observation_date)).mappings().all()
    counts = dict(conn.execute(select(observations.c.source, func.count()).group_by(observations.c.source)).all())
    n_revisions = conn.execute(select(func.count()).select_from(revisions)).scalar()
with (root / 'observations.jsonl').open('w') as f:
    for r in records: f.write(json.dumps(json_record(r))+'\n')
samples=[]
for source in ['worldbank', 'ecb', 'treasury']:
    samples.extend([r for r in records if r['source']==source][-3:])
with (root / 'sample_records.sql').open('w') as f:
    f.write('-- Real normalized samples. Run schema.sql first on an empty PostgreSQL database.\nBEGIN;\n')
    for r in samples:
        f.write(str(observations.insert().values(**r).compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds':True}))+';\n')
    f.write('COMMIT;\n')
events=[json.loads(l) for l in Path('data/http_evidence.jsonl').read_text().splitlines()]
for e in events:
    if 'raw_path' in e:
        assert hashlib.sha256((Path('data')/e['raw_path']).read_bytes()).hexdigest()==e['sha256']
assert counts == {'ecb':15330, 'treasury':6487, 'worldbank':6}, counts
result={'database_engine_verified':db.dialect.name,'counts':counts,'total_records':len(records),
        'distinct_revision_snapshots':n_revisions,'http_attempts_archived':len(events),
        'http_successes':sum(e.get('status')==200 for e in events),
        'raw_checksums_verified':True,'postgresql_integration_verified':False}
(root/'verification_summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

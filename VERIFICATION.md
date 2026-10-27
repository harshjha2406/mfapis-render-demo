# Verification and delivery status

Review date: 27 October 2026. Distinguish the original build from the subsequent Mac demonstration.

## Current Mac demonstration

| Check | Evidence and result |
|---|---|
| Live extraction into PostgreSQL | `live_etl_run.log`: HTTP 200 downloads and `pipeline_success` with `database: postgresql` for all three sources |
| Stored observations | `evidence/database_counts.txt`: ECB 15,330; Treasury 6,487; World Bank 6; total 21,823 |
| Automated tests on Mac | User shared terminal result: 21 passed, 1 warning, no skips. The full Mac pytest log is not included |
| Observations API | Saved India GDP response in `evidence/worldbank_india.json`; HTTP 200 shown in user-provided server output |
| Conversion API | Saved USD/INR response in `evidence/fx_conversion.json`; HTTP 200 shown in user-provided server output |
| Local validation summary | `evidence/VALIDATION.md` |

The PostgreSQL run is supported by uploaded pipeline logs and query output. The passing PostgreSQL
test result is user-reported terminal evidence; the reviewer did not independently rerun PostgreSQL.
The reason for the warning in the Mac run cannot be established from its summary alone.

## Archive review

- ZIP integrity check passed.
- Source catalogue contains 18 entries covering all ten categories, A–J.
- The normalized export contains 21,823 records with 21,823 distinct composite keys.
- All exported source hashes resolve to included raw files.
- All six raw response files match their SHA-256 filenames.
- The HTTP manifest contains 11 successful requests: seven original build requests and four Mac requests.
- Each manifest response has matching archived bytes, byte count and SHA-256.
- Saved JSON responses parse successfully; FX amount calculation agrees with the supplied rate.
- `.env`, the virtual environment and local database files are absent. The setup example uses placeholders.
- A targeted credential scan found no apparent live credentials; this is not a guarantee against every secret format.

## Original build evidence retained

`test_results.txt` contains the original Python 3.12 build result: 20 passed, 1 PostgreSQL test skipped,
and a Starlette/httpx deprecation warning. It is not the later Mac test run.

`exports/verification_summary.json` records the original SQLite export and its original seven-request
snapshot. Its `postgresql_integration_verified: false` describes that build environment only.
Additional metadata points to the later Mac evidence without altering the historical result.

`exports/observations.jsonl` and sample exports remain the original build snapshot. Later Mac
downloads and API responses retain their own retrieval timestamps and hashes. These are distinct captures.

The original build also exercised incremental updates, replay, duplicate prevention, changed-value
snapshots, transactional rollback, non-regressing checkpoints, missing values, pagination, retries,
HTTP error handling, schema compilation and local API behavior.

## Reproduction and scope

Follow `START_HERE.md` for setup. The PostgreSQL test requires a separate empty database and leaves
test records behind. Create a new empty test database for a repeat run; do not target production data.

The package includes source research, three modular pipelines, raw responses, normalized data,
PostgreSQL schema, tests, API examples, licensing notes, opportunity ranking and pricing proposals.
Commercial rights, customer demand, production deployment, load testing, backup restoration,
authentication, billing and a measured SLA remain outside the completed demonstration.

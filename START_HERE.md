# MFAPIs: start here

This is a research and ETL proof of concept for the assignment, prepared on 26 October 2026. It includes real downloaded data, three modular pipelines, a source catalogue across all ten categories, proposed commercial products, tests and a local demonstration API.

**Current local validation:** The Mac demonstration loaded 21,823 observations into PostgreSQL 16. `live_etl_run.log` records successful PostgreSQL loads for World Bank, ECB and Treasury. The user-reported test run returned 21 passed and 1 warning, with no skips; its full terminal log was not included in this archive. Saved API responses and query output are in `evidence/`. The original build used SQLite and its historical test output is retained. This is a local prototype, not a deployed or commercially licensed service.

## Understand the project in five minutes

- **API:** a URL that returns structured information to another program.
- **Extract:** download the source data.
- **Transform:** make fields, dates, units and missing values consistent.
- **Load:** save the cleaned records in a database.
- **PostgreSQL:** the database required by your assignment.
- **SQLAlchemy:** the Python library that sends records to the database.
- **Pandas:** used here for tabular data-quality summaries.
- **Incremental update:** reprocess recent observations and insert/update records without creating duplicates.

Read `REPORT.md` first for the business recommendation. Read `SOURCES.md` for source details. Read `VERIFICATION.md` for the evidence, its provenance and remaining production work.

## 1. Install your tools

On your laptop, install Python 3.12 or later, VS Code and Docker Desktop. Start Docker Desktop. Extract this ZIP, then open the `mfapis_project` folder in VS Code. Open Terminal → New Terminal. Run every following command from this folder, where `requirements.txt` lives.

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, replace `python` in commands below with `.\.venv\Scripts\python.exe` and `uvicorn` with `.\.venv\Scripts\uvicorn.exe`. You do not need to change PowerShell's execution policy.

## 2. First run: understand the data without Docker

```bash
python -m mfapis.replay --database-url sqlite:///learning.db
python -m pytest -q
```

Replay loads the real, saved 2024–2025 responses supplied in this package; it makes no new HTTP request. SQLite is only a learning/smoke-test path. The PostgreSQL integration test will be skipped until a separate test database URL is supplied.

Open the three files in `data/samples/`. Compare one normalized record with its raw source response through `raw_sha256`. `data/http_evidence.jsonl` records URL, UTC timestamp, response status, byte count and SHA-256 for every archived request.

## 3. Start PostgreSQL

Copy `.env.example` to `.env` using your file manager. Edit both password occurrences to the same strong local password. Use a URL-safe password for this beginner setup; otherwise URL-encode it in `DATABASE_URL`. Never publish `.env`.

```bash
docker compose up -d --wait
```

Set `DATABASE_URL` in the terminal (Python does not automatically read `.env`):

**Windows PowerShell:**

```powershell
$env:DATABASE_URL="postgresql+psycopg://mfapis:YOUR_PASSWORD@localhost:5432/mfapis"
```

**macOS/Linux:**

```bash
export DATABASE_URL='postgresql+psycopg://mfapis:YOUR_PASSWORD@localhost:5432/mfapis'
```

Replace `YOUR_PASSWORD` with the password in `.env`. Keep the local database bound to localhost as in `compose.yaml`.

## 4. Load real records into PostgreSQL

First prove the database works using the saved responses:

```bash
python -m mfapis.replay
```

Then extract fresh source data, using a reproducible historical range:

```bash
python -m mfapis.cli all --start 2024-01-01 --end 2025-12-31 --full
```

Run one category separately if learning:

```bash
python -m mfapis.cli worldbank --start 2024-01-01 --end 2025-12-31 --full
python -m mfapis.cli ecb --start 2024-01-01 --end 2025-12-31 --full
python -m mfapis.cli treasury --start 2024-01-01 --end 2025-12-31 --full
```

Omit `--end` to include observations through today. Run again without `--full` to exercise the checkpoint/overlap logic. Macro rechecks three years; daily sources recheck seven days. Schedule a monthly `--full` reconciliation of your configured history to catch older corrections. The ECB static XML is downloaded in full, then filtered locally.

## 5. Inspect your PostgreSQL records

```bash
docker compose exec db psql -U mfapis -d mfapis -c "SELECT source, COUNT(*) FROM observations GROUP BY source;"
docker compose exec db psql -U mfapis -d mfapis -c "SELECT * FROM watermarks;"
```

Record the counts, rerun the exact same extraction range and confirm counts are unchanged unless the source added observations. An updated value should change the current observation and add a distinct revision snapshot. It should not add a second current record for the same key.

## 6. Run the real PostgreSQL integration test

Create a separate empty test database:

```bash
docker compose exec db createdb -U mfapis mfapis_test
```

Set `TEST_DATABASE_URL` using the same command style as `DATABASE_URL`, replacing the database name with `mfapis_test`. Then:

```bash
python -m pytest -q
```

The test deliberately refuses a nonempty observations table; create a new empty test database for another run and point `TEST_DATABASE_URL` at it. It never deletes your existing data. Keep the test result as evidence. If this test fails, do not report PostgreSQL verification as complete.

## 7. Open the demonstration API

```bash
uvicorn mfapis.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` in your browser. Try:

```text
GET /v1/observations?source=worldbank&entity=IND
GET /v1/observations?source=treasury&metric=par_yield_10Y
GET /v1/observations?source=ecb&entity=EUR/USD
GET /v1/fx/convert?base=USD&quote=INR&amount=100&on=2025-12-31
```

Use an exact date present in `observations`. Weekends/holidays return 404 for conversion; the API does not quietly substitute another date. The demo has no authentication or billing and should stay local.

## Your seven-day learning plan

| Day | Work to do yourself | Evidence to retain |
|---|---|---|
| 1 | Read the assignment and catalogue. Open each source/terms page. Explain why the three selected datasets fit the scope. | Annotated catalogue; three-source selection |
| 2 | Run World Bank ingestion. Understand one JSON response and pagination. | Raw response, HTTP log, field mapping |
| 3 | Run ECB and Treasury ingestion. Understand XML and different units. | All three real extracts |
| 4 | Start PostgreSQL, replay real data, inspect tables. | Query outputs and schema |
| 5 | Run fresh ETL twice; explain duplicates, nulls and revisions. | Before/after counts and sample JSON |
| 6 | Run tests including PostgreSQL. Try an unavailable date, a missing value and an HTTP failure in tests. | Test log and limitation list |
| 7 | Review licensing, pricing assumptions and recommendation. Rehearse a five-minute demo. | Code ZIP, report, catalogue and evidence |

## Five-minute demonstration script

1. Explain the problem: clients need consistent, traceable financial data across incompatible public sources.
2. Show the ten-category catalogue and why a public URL is not a resale licence.
3. Show one real archived request and the matching normalized JSON.
4. Run a pipeline and query PostgreSQL. Repeat it to demonstrate duplicate prevention.
5. Show a passing PostgreSQL test and local API response; explain limitations and proposed pricing.

If asked why someone would pay for free underlying data: the product is reliable normalization, provenance, revision handling, integration support and delivery. Customer willingness to pay still needs to be tested.

## Common problems

| Symptom | Next action |
|---|---|
| `python` not found | On Windows use `py -3.12`; on macOS/Linux check `python3`. |
| `ModuleNotFoundError` | Install requirements with the Python inside your project virtual environment. |
| Database connection refused | Start Docker Desktop; inspect `docker compose ps`. |
| Database authentication failed | Compare `.env` password and `DATABASE_URL`; changing `.env` does not reset a password in an existing database volume. |
| HTTP 403 | Respect the block; use saved replay for the demo and investigate the source policy. |
| No rows for a date | Check holidays, release lag, annual versus daily frequency and your date range. |
| PostgreSQL test skipped | Set `TEST_DATABASE_URL` to a separate empty PostgreSQL test database. |

Stop the local database with `docker compose stop` when finished. This preserves its data.

## Restarting the demonstrated Mac setup

For the existing Mac project with its saved, URL-encoded DATABASE_URL, open Docker Desktop,
then run these commands from the project folder. Keep the API terminal open.

```bash
source .venv/bin/activate
set -a
source .env
set +a
docker compose up -d --wait
./.venv/bin/python -m uvicorn mfapis.api:app --host 127.0.0.1 --port 8000
```

The archive excludes `.env`; a new installation must first create its own settings using step 3.

`export_evidence.py` is a fixed 2024–2025 demonstration exporter. Its expected counts are hardcoded,
and its PostgreSQL integration flag is not a test result. Do not use a newly generated export summary
as proof that the integration test ran; retain the actual test output separately.

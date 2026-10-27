# Deployment update — 27 October 2026

## Added

- Responsive dashboard served by the same FastAPI service; no separate frontend server, CDN or Node build required.
- Dataset catalogue and database readiness endpoints.
- Verified snapshot importer with atomic bulk loading, source locks, revision snapshots and checkpoints.
- Render Blueprint for a free Python service and a free PostgreSQL 16 instance in Singapore.
- PostgreSQL URL normalization for the installed psycopg 3 driver, including encoded passwords.
- Generic public database errors that do not reveal credentials or SQL.
- API requests no longer create database tables; initialization happens before startup.
- Nine additional automated test cases, including URL variants, idempotency, corrupt snapshot rollback, real API data and failure handling.

## Validation and limits

29 tests passed, one PostgreSQL integration test skipped, one Starlette/httpx deprecation warning.
Executed on Python 3.12 in the preparation environment. Render is configured for Python 3.13.6, matching the user's original Mac setup.
New database bootstrap behaviour was tested with SQLite; a new PostgreSQL integration run was not possible here.
The earlier original pipeline was demonstrated on PostgreSQL by the user, as preserved in the original evidence.

A Chromium browser check exercised the real-data local server: GDP country switching, FX paging/date filters,
Treasury maturity selection, empty ranges, exact-date conversion, missing-date errors, CSV download and 390px mobile layout.
No JavaScript exceptions were observed. Browser test dependencies are not required to deploy.

No new provider HTTP downloads or real-time feed are claimed. The snapshot preserves the original source timestamps.
The YAML was reviewed against Render's official documentation but has not been submitted to Render's account API for validation.
No cloud service was created, no cost incurred and no public URL verified during preparation.

The prior assignment docs and historical test outputs are retained. README.md and RENDER_DEPLOY.md describe this release.

# Current release: MFAPIs 0.3.0

Start with [UPGRADE.md](UPGRADE.md) to update the existing Render service with latest FX and source refresh. Read [LIVE_UPGRADE_NOTES.md](LIVE_UPGRADE_NOTES.md) for changes, validation and remaining production work.

The material below describes the earlier historical-data deployment and is retained for context; its no-refresh statements no longer describe release0.3.0.

---

# MFAPIs — Financial Data Explorer

A browser dashboard and FastAPI service backed by PostgreSQL, prepared for Render.

**Deploy:** follow [RENDER_DEPLOY.md](RENDER_DEPLOY.md). Upload this folder's contents to a GitHub repository so `render.yaml` is at the root. Create a Render Blueprint from that repository.

**Deployment status:** prepared and tested locally; no public Render deployment or public URL has been verified yet.

## Dashboard

The home page `/` shows real historical GDP growth, EUR reference exchange rates and US Treasury yields.
It includes source and date filters, charts, paginated tables, CSV download, normalized JSON and a currency converter.
Initial data covers 2024–2025, with 21,823 observations. It is not a real-time feed and has no scheduled updates.

## Startup

`render.yaml` defines a Python web service plus PostgreSQL 16, both on free plans.
The startup importer verifies snapshot and raw-response checksums before seeding an empty database in one transaction.
Existing observations are retained on restart. Render supplies DATABASE_URL; local passwords are not needed.

## API routes

- `/` — dashboard
- `/docs` — interactive API documentation
- `/healthz` — readiness check requiring all three sources
- `/v1/catalogue` — counts, coverage, available series and source metadata
- `/v1/observations` — filtered normalized observations
- `/v1/fx/convert` — exact-date reference conversion

## Verification

The deployment update passed 29 tests locally; one PostgreSQL integration test was skipped because a server was unavailable.
The browser check covered charts, filters, paging, conversion, unavailable dates, CSV download and mobile overflow.
See `evidence/render_test_results.txt`, `evidence/render_browser_checks.json` and `DEPLOYMENT_CHANGES.md`.
The earlier assignment's Mac PostgreSQL test result of 21 passed applies to that earlier version.
The new deployment bootstrap still requires validation on the actual Render PostgreSQL instance.

## Original assignment

- `REPORT.md`: business recommendation and original demonstration results.
- `SOURCES.md`: 18 source entries across ten categories.
- `OPPORTUNITY_MATRIX.md`: opportunity ranking and pricing assumptions.
- `START_HERE.md`: original local setup and learning guide.
- `VERIFICATION.md`: original assignment evidence reconciliation.
- `data/` and `exports/`: archived real responses and normalized snapshot.
- `tests/`: pipeline and deployment tests.

This is a read-only demonstration with no authentication, billing or production SLA. Commercial redistribution remains subject to source terms.
Render free web services sleep when idle; free databases expire after 30 days. See the deployment guide before promising continued availability.

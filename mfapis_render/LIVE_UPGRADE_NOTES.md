# MFAPIs 0.3.0 — updated FX and source refresh

The previous deployment seeded real observations ending in 2025 and never refreshed them. The reviewer asked for updated rates and a usable currency selector, referencing Twelve Data's exchange-rate API.

## Implemented behavior

- `GET /v1/exchange-rate?symbol=USD/INR`: latest permitted Twelve Data quote, explicit provider timestamp and freshness. No hardcoded/demo-key fallback.
- `GET /v1/fx/convert?base=USD&quote=INR&amount=100`: latest quote plus precise conversion. Supplying `on=YYYY-MM-DD` selects the existing exact-date ECB path instead.
- `GET /v1/fx/currencies`: enabled currency names/pairs and public configuration status; never exposes credentials.
- Latest/historical mode selector, currency dropdowns with names, valid pair filtering, swap, amount input, quote timestamp, JSON output, auto-refresh checkbox, and error states. Latest FX is the default screen. Mobile layout is preserved.
- Sixty-second persistent quote cache, five-minute default maximum quote age, no stale fallback, persistent per-minute/day upstream budgets, one bounded retry for network/HTTP 5xx failures, authentication/quota cooldowns, and same-pair request coalescing.
- Original response bytes/hash and provider/retrieval timestamps are stored with the current cached quote. This is a rolling per-pair cache, not a historical tick archive. Retention must match your provider agreement.
- Configurable historical refresh on startup/every 6 hours while awake; durable raw public-source responses and per-source success/error status in PostgreSQL. Failures retain existing rows and do not mark the old data fresh.
- Additive database tables are registered by startup bootstrap. Original observation keys, revisions, watermarks and data are retained.

## Evidence

Local tests: **60 passed, 1 skipped, 1 warning**. The skip is the opt-in PostgreSQL integration test; the warning is the existing Starlette/httpx TestClient deprecation. Eight browser checks passed with no JavaScript errors. Details are under `evidence/live_*`. Real-source refresh on 28 October 2026 UTC produced:

| Source | Stored observations after refresh | Latest observation |
| --- | ---: | --- |
| ECB | 21,449 | 2026-10-28 |
| Treasury | 9,178 | 2026-10-28 |
| World Bank | 6 | 2025-12-31 annual label |

Four real HTTP response bodies and their hashes are in `evidence/refresh_raw`; the ingestion log and summary identify SQLite as the local validation store. They are evidence, not automatically imported in deployment: the deployed service fetches current source data itself after bootstrapping.

`evidence/twelvedata_public_demo_check.json` records a real request using the provider's public demo key. `evidence/twelvedata_adapter_smoke.json` records a real successful adapter call for EUR/USD, HTTP 200, with a provider quote age of 152 seconds at retrieval. Neither establishes your personal key's entitlements. There is no real API key in the package. Tests use clearly labeled synthetic protocol fixtures only for deterministic success/failure scenarios; those fixtures are not loaded into the deployed application.

Browser tests exercise missing-key setup, actual historical conversion, latest-mode request/rendering via browser fixtures, swapping and selecting currencies, auto-refresh, stale-error handling and 390px layout. No claim is made that your account or the updated public deployment has been tested from this environment.

The PostgreSQL integration test remains skipped without a dedicated server. PostgreSQL-specific advisory-lock behavior and performance must be validated on the target service; the previously completed original project's PostgreSQL tests are separate evidence.

## Production scope

Basic per-client throttling is in-process; provider budgets are database-backed across replicas. Arbitrary public users can still use the shared allowance. Before commercialization, require authenticated customer keys, quotas, billing, monitoring, agreed uptime, operational backups, security/load testing and explicit licensing. Source freshness is not equal to trading execution quality. No payment, plan upgrade or subscription has been purchased.

Historical annual GDP cannot legitimately become a live financial quote. ECB daily reference rates and Treasury daily yields should retain their actual frequencies. Twelve Data handles latest FX; underlying price availability follows the provider/account, not an invented promise of constant updates.

## Primary reference sources reviewed

- https://twelvedata.com/docs/currencies/exchange-rate — pair request and rate/timestamp contract; auth also documented at https://twelvedata.com/docs
- https://support.twelvedata.com/en/articles/12520817-forex-api-v2 — feed behavior and separate API redistribution agreement
- https://twelvedata.com/terms — access, public display, redistribution and competitive-use restrictions
- https://support.twelvedata.com/en/articles/12647398-attribution-guidelines-for-using-twelve-data — public attribution
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html — daily reference-rate publication
- https://render.com/docs/free and https://render.com/docs/cronjobs — sleep and scheduled execution constraints

These are documentation references, not a legal clearance or a production certification.

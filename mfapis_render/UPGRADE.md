# Update your existing Render deployment

This is MFAPIs 0.3.0. It adds current-provider FX quotes and refreshes the historical source data. It does not deploy itself or contain your API key.

## 1. Upload the revised files to your existing repository

1. Unzip `MFAPIs_Render_Deployment.zip` on your Mac.
2. Open the `mfapis_render` folder. Its contents include `render.yaml`, `requirements.txt`, and the `mfapis` folder.
3. Open https://github.com/harshjha2406/mfapis-render-demo in your browser.
4. Select **Add file → Upload files**. Drag the CONTENTS of `mfapis_render` into the repository root, replacing matching files. Do not upload the enclosing folder or the ZIP itself.
5. Commit with the message `Add latest FX quotes and automatic source refresh`.

Keep the existing database and web-service names. Do not create another Blueprint or delete your database. The startup command adds new tables and retains existing observations. Old submission evidence remains historical evidence; new upgrade checks live in `evidence/live_*` and `evidence/twelvedata_*`.

## 2. Configure your provider key privately

In Render, open **mfapis-harsh-demo → Environment → Add environment variable**:

| Key | Value |
| --- | --- |
| `TWELVE_DATA_API_KEY` | Your actual Twelve Data API key |
| `AUTO_REFRESH_HISTORY` | `true` |

Save and deploy. The API key must be entered only in Render's private environment settings. Do not add it to GitHub, `render.yaml`, screenshots, browser JavaScript, or a chat message.

The Blueprint also supplies these defaults. Set them manually if your Blueprint has not synced:

| Key | Default | Meaning |
| --- | --- | --- |
| `FX_CACHE_SECONDS` | `60` | One stored provider quote per pair for up to 60 seconds |
| `FX_MAX_QUOTE_AGE_SECONDS` | `300` | Reject a quote whose provider timestamp is over 5 minutes old |
| `FX_PROVIDER_REQUESTS_PER_MINUTE` | `8` | Shared application budget for upstream attempts |
| `FX_PROVIDER_REQUESTS_PER_DAY` | `800` | Shared application budget per UTC calendar day |

These are conservative application limits, not a statement about your account entitlements. Match them to your actual plan, allowing for other applications using the same key. An always-open page refreshing every minute could exceed 800 calls/day; shared caching, hidden-tab pausing and quotas reduce usage but do not create additional credits.

Optional: `FX_ALLOWED_PAIRS` is a comma-separated list such as `EUR/USD,USD/INR,GBP/USD,GBP/INR`. Default enabled currencies are EUR, USD, INR, GBP, JPY, CHF, AUD, CAD, NZD, SGD, HKD and CNY, with the specific pairs in `mfapis/fx.py`. Quote options depend on the selected base. Reverse directions share the canonical quote and are calculated by MFAPIs. Enabling a pair does not purchase provider coverage; the provider may still reject it for your plan.

## 3. Wait for deployment and test

Keep the existing start command:

```sh
python -m mfapis.bootstrap && python -m uvicorn mfapis.api:app --host 0.0.0.0 --port $PORT
```

The first step registers additive tables; it does not erase historical rows. When `AUTO_REFRESH_HISTORY=true`, the server starts a background history check after startup. Give it a minute to finish fetching the three sources. Logs should show `scheduled_refresh_success` for each source, or a specific error class if a provider fails.

Open:

- Dashboard: https://mfapis-harsh-demo.onrender.com/
- FX configuration (contains no key): https://mfapis-harsh-demo.onrender.com/v1/fx/currencies
- Latest rate: https://mfapis-harsh-demo.onrender.com/v1/exchange-rate?symbol=USD/INR
- Latest conversion: https://mfapis-harsh-demo.onrender.com/v1/fx/convert?base=USD&quote=INR&amount=100
- API docs: https://mfapis-harsh-demo.onrender.com/docs

Acceptance checks:

1. **Latest · Twelve Data** is selected by default. Pick different From/To currencies, enter an amount, and convert. Try Swap currencies.
2. A successful response has `mode: latest`, `provider: twelvedata`, `timestamp`, `as_of`, `quote_age_seconds`, `cached`, and `stale: false`.
3. The provider timestamp is reasonably recent. The value need not change every refresh: a market quote can remain unchanged, and cached responses retain the original timestamp.
4. Automatic refresh runs every 60 seconds while the FX tab and browser page are visible. Uncheck it to stop. It is HTTP polling, not tick streaming.
5. Choose **Historical · ECB daily reference**, enter 2025-12-31 and USD→INR, amount 100. The historical value is approximately INR 8,986.94. A weekend without observations returns a clear error.
6. History coverage should advance beyond 2025 after a successful source refresh. GDP remains annual: the latest completed year's label is not a real-time reading.
7. In `/v1/catalogue`, inspect the `refresh` entries, latest observation dates and last successful checks. The dashboard checks for newly ingested data once per minute.

Do not send the reviewer an updated-completion claim until these checks pass on Render with your own key.

## Troubleshooting

| Response | Action |
| --- | --- |
| `provider_not_configured` | Add `TWELVE_DATA_API_KEY`, save and redeploy. |
| `provider_authentication` | Check that the key is correct and the account has permission for the endpoint. |
| `pair_unavailable` | Try EUR/USD, then verify USD/INR or other pairs are included in your plan. |
| `unsupported_pair` | Pick an enabled dropdown pair or update `FX_ALLOWED_PAIRS`. |
| `provider_budget_exhausted` / `provider_rate_limited` | Respect `Retry-After`; verify account credits and other apps using the key. Do not repeatedly click Convert. |
| `stale_quote` | The provider returned an old timestamp. Do not relabel it as live; check feed status and market availability. Historical mode remains separate. |
| `provider_unavailable` | A network/provider request failed after bounded retries. Retry after the stated delay. |
| Database503 after uploading | Check the start command still runs `mfapis.bootstrap`, and that the existing `DATABASE_URL` is retained. |
| Browser still shows the old UI | Confirm Render deployed the new commit, then hard-refresh the page with Cmd+Shift+R. |

## What this release does and does not establish

This is an upgraded reviewable demonstration, not a claim of full commercial production readiness. It includes persistent quote caching, shared upstream credit budgets, validated Decimal calculations, bounded timeouts/retries, explicit staleness rejection, server-only credentials, original provider timestamps, request IDs, basic per-process abuse limits, error handling, source refresh status and provenance.

Before a paid commercial launch, complete tenant authentication/authorization, customer-level quotas and billing, shared gateway rate limits, migration/rollback and backup drills, metrics and alerting, load tests, an always-on hosting/scheduler plan, and verified provider rights. Your confirmation of account access is used for this integration, but API access alone does not establish resale or public API redistribution rights. Twelve Data requires appropriate agreements for redistribution; its terms also restrict competitive use. Agree the intended MFAPIs product with the provider before commercialization.

Free Render hosting can sleep. A background thread cannot run while it is asleep. The source checks run on startup and when due (every 6 hours after success; retry after 15 minutes after failure) while the process is awake. For guaranteed scheduled refresh, run `python -m mfapis.refresh --force` using a separately provisioned scheduler with the same database URL. No paid service is created by this package. Free database lifespan/availability remains a hosting constraint.

## Local verification

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

For a local run, load your `.env` with `DATABASE_URL` and optionally your key; run the same bootstrap and uvicorn commands above (use port 8000). Do not commit `.env`.

The PostgreSQL integration test is opt-in and requires a new, EMPTY disposable `TEST_DATABASE_URL`. Never point it at your deployment database. Ordinary tests use isolated SQLite files and test-only provider fixtures. See `evidence/live_test_results.txt` and `LIVE_UPGRADE_NOTES.md` for actual verification limits.

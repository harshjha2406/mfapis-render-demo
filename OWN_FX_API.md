# MFAPIs-owned exchange rate API — live-feed architecture

## What this upgrade does (and doesn't do)

The platform implements its **own** FastAPI endpoints, secure quote ingestion, PostgreSQL storage, history, bid/ask math, inverse-pair calculations, basic cross-rates and a 15-second browser refresh. **No rate is fetched from Twelve Data, Massive, or another quote aggregator at request time.**

The system **does not independently observe the global FX market**. Real-time prices require an authorized external **source of raw market observations**, for example a bank, liquidity provider, execution venue, or direct trading system connection. This is a market input, not a white-label currency-conversion API. Permission to publish/re-distribute the quotes is still required. Without fresh observations, the API returns HTTP 503, not made-up values. Neither the old Twelve Data nor Massive quote tables are used by this implementation.

**The 15-second refresh is a *dashboard polling interval*, not a promise that the market feed publishes a new price every 15 seconds.** The quote timestamp is the real event time, not the time the website requested it.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/v1/fx/currencies` | Currencies, pair metadata, configuration readiness |
| POST | `/v1/fx/quotes/ingest` | Authenticated source quote collector (private key in request header) |
| GET | `/v1/exchange-rate?symbol=USD/INR` | Latest eligible bid, ask, midpoint; never stale |
| GET | `/v1/fx/convert?base=USD&quote=INR&amount=100` | Conversion from market observations |
| GET | `/v1/fx/quotes` | Latest stored direct quotes with explicit `fresh` status |
| GET | `/v1/fx/history?symbol=USD/INR` | Recorded direct-quote history |
| GET | `/v1/fx/convert?base=USD&quote=INR&amount=100&on=2025-12-31` | Separate ECB *historical reference* conversion |

Your API documentation is at `/docs`. API responses always carry quote `source`, source observation timestamp `as_of`, quote age, and whether a cross-rate was derived.

## Data flow

```
YOUR AUTHORIZED REAL-TIME MARKET OBSERVATION SOURCE
                  |
         YOUR FEED ADAPTER
                  |
      JSON market quotes (bid / ask)
                  |
  POST /v1/fx/quotes/ingest + private server key
                  |
     MFAPIs-owned validation and PostgreSQL
                  |
       Inverse/cross-rate calculation
                  |
         MFAPIs public REST API
                  |
      MFAPIs dashboard (15s refresh)
```

### Expected quote body (schema, NOT an actual current price)

```json
{
  "symbol": "USD/INR",
  "bid": "<ACTUAL_BID_FROM_YOUR_SOURCE>",
  "ask": "<ACTUAL_ASK_FROM_YOUR_SOURCE>",
  "observed_at": "<UTC_TIMESTAMP_FROM_YOUR_SOURCE>",
  "source": "<NAME_OF_AUTHORIZED_FEED>"
}
```

The placeholders above are documentation, not a working request. **Do not invent values** or replace old timestamps with the current time; `observed_at` must come from the market observation. A quote older than `FX_MAX_QUOTE_AGE_SECONDS` or more than 5 seconds in the future is rejected. Duplicate timestamps are idempotent; older quotes cannot overwrite newer ones. Quotes from incompatible feeds are not silently mixed when building cross rates.

### Environment variables (configure privately on Render)

- `DATABASE_URL`: existing Render PostgreSQL connection URL
- `MFAPIS_INGEST_KEY`: random secret of >=32 characters; create locally with `openssl rand -hex 32`
- `FX_LIVE_DISPLAY_AUTHORIZED=false` by default; only set to `true` after an authorized feed is connected **and its rights allow this public API/display**
- `FX_REFRESH_SECONDS=15`: browser polling interval
- `FX_MAX_QUOTE_AGE_SECONDS=120`: reject old quotes
- `FX_ALLOWED_PAIRS=...`: optional pairs configured for your feed

Remove `TWELVE_DATA_API_KEY`, `MASSIVE_API_KEY`, and the previous provider-specific FX settings from Render once no code relies on them. Don't store secrets in GitHub or chat.

## Connecting your own feed

Write a small adapter for a data source whose bid/ask quote access and redistribution rights you control. It must output *real*, ISO-8601 timestamped quote JSON objects, one per line. The bundled generic publisher safely forwards these observations:

```bash
export MFAPIS_URL='https://mfapis-harsh-demo.onrender.com'
export MFAPIS_INGEST_KEY='<secret-that-matches-render>'
YOUR_AUTHORIZED_FEED_ADAPTER | python scripts/publish_quotes.py
```

The feed adapter is **not yet provided** because the specific bank, venue, or broker feed/protocol and authorized credentials are not known. Until then, public live quotes will be unavailable. For development tests, `tests/test_live_fx.py` uses synthetic fixtures only in a disposable test database.

## Deployment and testing

1. Back up the public demo branch before applying the patch; unzip the updated files at the **repo root** (not inside another nested directory).
2. Run `python -m pytest -q tests/` and ensure there are no failed tests.
3. Push the demo repo to GitHub and deploy to the existing Render service. The startup bootstrap creates two **new** owned quote tables; the ECB/Treasury/World Bank observations remain unchanged.
4. Set a private ingestion key in Render and keep `FX_LIVE_DISPLAY_AUTHORIZED=false` until a real authorized quote stream is working and display permission is documented.
5. With actual authorized quote input connected, enable display, verify `GET /v1/fx/currencies`, `GET /v1/exchange-rate?symbol=USD/INR` and quote `as_of` timestamps. Verify rates change only when fresh **source** observations change.
6. Update the same code in Girish's private repository, review `git diff --check`, and push normally (never force push).

### Security / commercial caveats

This is an **MVP**, not a fully commercial market-data operation. Production needs separate publisher authorization/rotation, per-client subscriber API keys, tenant rate limits across replicas, secrets management, monitoring, scalable streaming/subscriptions, stricter source provenance and quote-quality controls, contractual data rights, and stable SLAs. Do not present this product as a consolidated market price or an executable trade quote.

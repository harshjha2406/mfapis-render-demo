# MFAPIs Public-Data Expansion: Research and Prototype

Prepared 26 October 2026. Local validation updated 27 October 2026.

Research scope: ten financial data categories. Implemented scope: three specific datasets. Proposed prices and customer demand scores are hypotheses requiring customer validation. This project does not assume knowledge of MFAPIs’ existing catalogue, contracts, customers or infrastructure.

## Recommendation

Start with a **Macro & Reference Data API** combining macroeconomic indicators, daily reference FX and sovereign yield curves, with consistent units, dates, provenance and revision handling.

The initial commercial value is reliable delivery, normalization and integration support. The service should be positioned as informational financial data, with coverage and update frequency clearly stated.

The prototype implements:

- Annual GDP growth for India, the United States and the United Kingdom.
- ECB EUR reference exchange rates.
- US Treasury nominal par yield curves.

These datasets demonstrate three modular ingestion pipelines using public sources that do not require API keys. The prototype does not establish commercial demand or licensing clearance for every future dataset.

US company fundamentals are the strongest next-stage research candidate, with higher normalization effort.

**Validation status:** PostgreSQL storage was demonstrated locally on macOS using PostgreSQL 16 through Docker. The database contains 21,823 observations: ECB 15,330; Treasury 6,487; World Bank 6. Automated tests returned 21 passed and 1 warning, with no skipped tests. Both the observations and FX conversion endpoints returned HTTP 200. Saved API responses, database counts and a validation summary are available in the `evidence/` folder. Production deployment and commercial licensing clearance remain outside the completed prototype scope.

## Twelve Data Benchmark

The following pages were reviewed during the original research:

- Market-data catalogue: https://twelvedata.com/market-data
- Business pricing: https://twelvedata.com/pricing-business

Twelve Data offers equities, FX, crypto, ETFs/funds, commodities, fundamentals and related analytics. Its value includes common API formats, broad coverage and commercial entitlements.

The original research recorded Venture at **US$499/month** and Enterprise at **US$1,099/month**, billed monthly, on the review date. These are historical research observations and should be rechecked before use in a commercial proposal.

The business offering distinguishes external display from external distribution and lists additional exchange/data entitlements. The exact quote depends on selected capacity and licences. These prices are not a like-for-like comparison with this narrow prototype.

MFAPIs should initially address a focused integration problem: transparent source provenance, clear observation and retrieval dates, consistent schemas and customer support.

## What the Three Pipelines Deliver

| Category | Implemented dataset | Normalization | Coverage boundary |
|---|---|---|---|
| I: Macroeconomics | World Bank GDP growth, IND/USA/GBR | ISO3 country; indicator ID; annual year-end label; percentage change | One annual indicator; additional macro series and release calendars are future work |
| D: Forex | ECB EUR reference exchange rates | Quote currency per EUR; observation date | Daily informational reference rates; no executable prices or intraday candles |
| G: Fixed income | US Treasury nominal par curve | Maturity code; date; annual percentage yield | Yield curves rather than individual bond prices, zero-coupon discount factors or credit ratings |

The demonstration range is **1 January 2024 through 31 December 2025**.

Historical observations were downloaded from the sources during the project. Raw responses are preserved for inspection and replay. The raw ECB file contains additional history; only the requested dates are normalized for the demonstration.

## Local Demonstration Results

### Environment

- macOS
- Python 3.13.6
- PostgreSQL 16 through Docker
- SQLAlchemy database integration
- FastAPI local HTTP service

### PostgreSQL Records

| Source | Observation count |
|---|---:|
| ECB | 15,330 |
| US Treasury | 6,487 |
| World Bank | 6 |
| **Total** | **21,823** |

Counts refer to normalized observations, not unique instruments. A Treasury date can produce multiple observations because each maturity is stored separately.

### Tests and Pipeline Execution

- Archived-source replay completed successfully against PostgreSQL.
- The automated test run returned **21 passed, 1 warning**, with no skipped tests.
- The PostgreSQL integration test was included in that passing run.
- A subsequent live ingestion run reported pipeline success.
- The warning has not been classified in this validation summary.

### API Demonstration

The following local requests returned HTTP 200:

1. `/v1/observations?source=worldbank&entity=IND&limit=100`
2. `/v1/fx/convert?base=USD&quote=INR&on=2025-12-31&amount=100`

The FX response reported:

- Base currency: USD
- Quote currency: INR
- Observation date: 2025-12-31
- Calculated cross-rate: approximately 89.86936 INR per USD
- Input amount: 100 USD
- Converted amount: approximately 8,986.94 INR

The cross-rate and converted amount are calculated by MFAPIs from ECB reference rates. They are informational values rather than executable trading quotes.

### Saved Evidence

| File | Purpose |
|---|---|
| `evidence/fx_conversion.json` | Saved currency conversion API response |
| `evidence/worldbank_india.json` | Saved India GDP growth API response |
| `evidence/database_counts.txt` | PostgreSQL observation counts |
| `evidence/VALIDATION.md` | Local validation summary |

The original package’s test results and verification metadata describe its earlier build environment. This section and `evidence/VALIDATION.md` record the subsequent successful PostgreSQL demonstration on the local Mac.

## Source Discovery and Coverage Gaps

`SOURCES.md` and `source_catalogue.json` contain 18 entries across categories A–J, including providers, fields, extraction method, frequency, historical availability, authentication, extraction outcome and rights status.

They distinguish documentation review from successful dataset extraction.

| Category | Practical route | Gap before a comprehensive product |
|---|---|---|
| A: Equities | Listing directories plus a licensed price/corporate-action provider | Global symbol identity, adjusted prices, survivorship, calendars and redistribution contracts |
| B: Fundamentals | SEC XBRL, submissions, 13F and insider filings | Taxonomy mapping, fiscal calendars, amendments, ratios and non-US coverage |
| C: ETFs | SEC N-PORT plus issuer/vendor sources under agreed terms | Daily NAV/holdings, expense histories, global mapping and matching-date premiums |
| D: Forex | Central-bank reference series | Intraday execution data and broader currency/calendar coverage |
| E: Cryptocurrency | Exchange or aggregator agreements | Venue aggregation, supply/market-cap methodology and downstream rights |
| F: Commodities | EIA and World Bank benchmark series | Contract specifications, tradable settlements, metals licensing and roll conventions |
| G: Fixed income | Official sovereign curves and additional government security feeds | Security master, coupon/maturity history, global issuers and licensed ratings |
| H: Indices | Index-provider licences | Constituents, weights, historical membership and branding/benchmark permissions |
| I: Macroeconomics | World Bank and selectively licensed FRED/original-publisher series | Release calendars, revisions/vintages, higher-frequency series and country expansion |
| J: Analytics | Calculations over permitted input data | Tested methodology, adjusted prices, sufficient history and derivative-output rights |

The source catalogue is a discovery baseline. A source does not cover every requested field merely because it appears under a category.

## Commercial Opportunity Ranking

`OPPORTUNITY_MATRIX.md` contains all seven evaluation criteria and reproducible weighted scores.

Demand and subscription potential are analyst judgments; no customer interviews were conducted. Licensing clearance is a launch requirement independent of the score.

1. **Macroeconomic indicators — 85/100.** Low ingestion cost and broad contextual use; differentiation requires consistent metadata and revision support.
2. **Reference FX — 83/100.** Clear integration use, although strong free alternatives limit pricing power.
3. **Sovereign yield curves — 83/100.** Useful for treasury and risk workflows; initial coverage is deliberately narrow.
4. **Company fundamentals — 81/100.** Strong differentiation potential with significantly greater normalization and quality requirements.

The remaining ranking is provided in the matrix. Small score differences should not determine investment: changing one licensing rating by one point changes the total by four points.

## Five Customer Segments

| Segment | Specific problem | Initial product/use |
|---|---|---|
| Fintech and accounting software teams | Inconsistent currencies and dates in cross-border dashboards | Reference FX conversion and historical snapshots |
| Wealth platforms and advisers | Economic and interest-rate context for portfolios | Macro indicators and sovereign curves with clear observation dates |
| Brokers and financial-content platforms | Reliable contextual widgets and explainers | Macro and curve APIs alongside separately licensed market prices |
| Banks and treasury/risk teams | Repeatable source data for internal reporting | Curve history, reference FX, provenance and controlled updates |
| Developers and AI financial-application teams | Unsupported or stale financial facts | Source-linked observations with units and retrieval timestamps |

These are prospective segments, not confirmed MFAPIs customers. AI outputs should retain source dates and units. Retrieval time alone does not establish economic freshness.

## Top-Three Product Proposals

All prices below are **proposed validation prices in USD per month**, excluding taxes, specialised data licences and bespoke support. They are not live offers.

Customer interviews, paid conversions and measured service costs should inform final pricing.

| Product | Target buyer | Proposed API design | Pricing experiment | Initial go-to-market |
|---|---|---|---|---|
| Macro Context | Wealth, AI and research product teams | `/v1/macro/series`, `/v1/macro/observations`, later `/v1/macro/revisions` | $29 developer: 25k requests; $149 team: 250k; enterprise by quote | Interview 10 teams; publish an example with source provenance; secure two paid pilots |
| Reference FX | Accounting, expense and cross-border dashboard teams | `/v1/fx/rates`, `/v1/fx/convert`, `/v1/fx/currencies` | $19 developer: 50k requests; $99 team: 500k; enterprise by quote | Demonstrate historical conversion; approach accounting SaaS teams; measure onboarding time |
| Sovereign Curves | Wealth, treasury and risk developers | `/v1/curves`, `/v1/curves/observations`, later `/v1/curves/spreads` | $49 developer: 25k requests; $199 team: 250k; enterprise by quote | Offer a reproducible curve-history demonstration; develop requirements with two risk teams |

The paths above are proposed product designs. The implemented endpoints are:

- `/v1/observations`
- `/v1/fx/convert`

`openapi.json` documents the implemented endpoints.

A future bundle could be tested at $249/month. Unavailable endpoints and unmeasured uptime commitments should not be included in a live offer.

Each plan should define API call limits, per-key rate limits, caching, permitted downstream use and attribution. An MFAPIs subscription cannot expand the rights granted by the original source.

Billing, account management, API keys, metering and customer agreements are not implemented in this prototype.

### Illustrative Economics

At 20 customers paying $149/month, monthly recurring revenue would be $2,980.

Assuming:

- $250 monthly infrastructure costs;
- $600 monthly support and maintenance allocation;
- 3% payment processing costs, equal to $89.40;

the contribution before other costs would be $2,040.60, or approximately 68.5%.

At ten customers paying the same price, the contribution would be $595.30, or approximately 40.0%.

These are arithmetic scenarios, not verified operating costs or revenue forecasts. They exclude initial engineering, sales, tax, full staffing and data-licence fees.

With the assumed $850 fixed monthly allocation and 3% payment cost, approximately six customers paying $149 cover those particular costs.

Demand, churn and support burden remain unmeasured.

### Launch Decision Criteria

Within a 30-day validation period:

1. Conduct five substantive customer interviews per priority product.
2. Secure two paid pilots for the bundle or strongest standalone product.
3. Demonstrate that at least one recurring customer workflow saves meaningful engineering time.
4. Measure API usage and support hours.
5. Reassess the product scope if customers prefer direct free sources and show little willingness to pay.

## Architecture and Data Contract

1. A connector requests a provider response using bounded timeouts and retries.
2. Decoded response entity bytes are saved by SHA-256 before parsing. HTTP transport compression is not retained.
3. A source-specific parser produces a shared observation record and validates identifiers, dates and finite numeric values.
4. A transaction upserts current observations, retains distinct value snapshots and advances the source checkpoint together.
5. The local read API exposes normalized records, units and attribution. FX conversion derives a cross-rate for an exact available date.

The primary key is:

`(source, entity, metric, observation_date, unit)`

PostgreSQL stores numeric values in `NUMERIC(30,12)`.

JSON emits decimal strings. Missing values remain JSON null and are not converted to zero.

Annual GDP uses December 31 as the annual period label, not the release timestamp.

Daily curve values remain percentages: a value of `4.2` means 4.2%, not 0.042.

Each record carries:

- `raw_sha256`
- `source_url`
- `retrieved_at`

Raw files and HTTP manifests support replayability.

`observation_revisions` retains unique content snapshots observed by this service. It does not reconstruct a complete historical point-in-time vintage database. An old value that disappears and later returns has one content snapshot rather than a separate event for each recurrence.

## Reliability and Data Quality

Implemented controls include:

- 10-second connection and 40-second read timeouts.
- Three attempts for transient network errors, HTTP 429 and selected 5xx responses.
- Backoff and Retry-After handling.
- No retries intended to bypass HTTP 403 restrictions.
- Raw archives for failures as well as successful responses.
- Structured JSON logging.
- Validation failures that stop the source load.
- Atomic data loading and checkpoint updates.
- Primary keys and upserts for duplicate prevention.
- Source advisory transaction locks on PostgreSQL.
- Pagination checks for World Bank extraction.

Missing values are retained and labelled. Invalid observations fail the source batch rather than silently disappear.

ECB exchange rates must be positive. Treasury yields may be zero or negative in principle.

The prototype does not apply linear interpolation or undisclosed holiday forward-filling.

Unexpected source structures fail clearly. Historical corrections outside the incremental overlap require scheduled full reconciliation.

### Operational Limitations

The prototype does not include:

- Distributed scheduling and alerting.
- A database migration manager.
- Service authentication and customer entitlements.
- Billing and API usage metering.
- Backup and restore verification.
- Production monitoring.
- A measured freshness or uptime SLA.

The API is demonstrated locally. Source providers do not supply an end-to-end availability guarantee for an MFAPIs service.

Larger-scale deployment would require batching, efficient bulk loading, caching, historical reconciliation and a controlled publication process.

Concurrency should be limited to one scheduled writer per source in this prototype. PostgreSQL locking serializes database loads, but fetching occurs before the lock. A single scheduler helps prevent an older fetched batch from overwriting newer observations.

## Licensing Findings That Affect the Business Model

These findings summarize the original research and require source-specific confirmation before commercial launch.

- **ECB:** Published reuse conditions require credit, accurate reproduction, disclosure of modifications and disclosure that the original source data are available free. Paying users should receive the required disclosure in the purchase flow as well as responses. A response field alone does not meet a pre-purchase disclosure requirement.  
  https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html

- **World Bank:** Default dataset reuse is under CC BY 4.0 with additional terms and possible third-party exceptions. GDP-growth metadata links that licence; each additional series requires its own review.  
  https://data.worldbank.org/summary-terms-of-use

- **US Treasury:** Government-origin data is a promising route, but this project has not established a blanket international redistribution grant. Source-specific clearance should be documented before commercial launch.  
  https://www.usa.gov/government-copyright

- **SEC:** Government-created and public filing content is described as reusable. Identifier rights and source limitations still require attention.  
  https://www.sec.gov/about/webmaster-frequently-asked-questions

- **Coinbase and CoinGecko:** Public technical access alone is insufficient to establish permission to resell a downstream data API. Review the applicable terms and obtain the necessary commercial agreement.  
  https://www.coinbase.com/legal/market_data  
  https://www.coingecko.com/en/api_terms

- **Indices and exchange prices:** Obtain explicit contracts covering the intended display, redistribution and derived uses.  
  https://www.spglobal.com/spdji/en/about-us/data-index-licensing/

Maintain a rights register containing the dataset owner, terms URL, review date, attribution requirements, permitted uses, geographic restrictions and approval status.

Commercial access should be enabled only where the intended use is permitted. Successful technical extraction does not establish commercial redistribution rights.

## Final Product Decision

Use the three implemented datasets to demonstrate a consistent, auditable financial data layer, then validate the Macro & Reference bundle with prospective customers.

Prioritise deeper coverage, reliable metadata and operational reliability. Research US company fundamentals as the next opportunity for differentiation.

Defer real-time exchange prices, comprehensive cryptocurrency feeds and commercial indices until contracts and unit economics justify them.

**PostgreSQL verification is complete for the local demonstration.** The database contains 21,823 observations, the test suite returned 21 passed with 1 warning, and both implemented API endpoints returned HTTP 200 in the demonstrated requests.

See `evidence/VALIDATION.md` and the saved API responses for the local demonstration results.
# Source catalogue

Reviewed 26 October 2026. `HTTP 200 archived` means an actual packaged data response. `Documentation reviewed` does not mean extraction or redistribution was verified. URLs below are official discovery/documentation/terms URLs; successful selected-source request URLs are in `data/http_evidence.jsonl`.

## A1 — Nasdaq symbol directory

- **Category:** A. Equity market data
- **Url:** https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs
- **Coverage:** US Nasdaq and other US exchange listings
- **Fields:** Symbol; security name; market category; ETF flag; test issue; financial status
- **Extraction method:** Delimited files; field definitions on page
- **Update frequency:** Current trading-day snapshots
- **Historical availability:** Current master; archive snapshots yourself, not a historical delisting database
- **Authentication:** No key for public directory
- **Extraction outcome:** Official documentation reviewed; file ingestion not implemented
- **Commercial redistribution:** Public access established; commercial redistribution permission not established for the directory. Confirm in writing before sale.
- **Terms url:** https://www.nasdaqtrader.com/trader.aspx?id=copydisclaimmain
- **Coverage gaps:** No OHLCV; no worldwide master; symbol changes need temporal identifiers.

## A2 — Alpha Vantage equity and calendar endpoints

- **Category:** A. Equity market data
- **Url:** https://www.alphavantage.co/documentation/
- **Coverage:** Selected global securities; exact symbol and endpoint coverage require validation
- **Fields:** Daily date/open/high/low/close/volume; dividend/split; company overview; IPO/earnings calendar; gainers/losers
- **Extraction method:** JSON/CSV API
- **Update frequency:** Endpoint-dependent: daily, intraday or event-based
- **Historical availability:** Daily history advertised as 20+ years; plan and symbol dependent
- **Authentication:** API key; endpoint/plan entitlements
- **Extraction outcome:** Documentation and terms reviewed; no authenticated extraction performed
- **Commercial redistribution:** Default terms are personal/noncommercial; written commercial agreement required. A paid key alone is not resale permission.
- **Terms url:** https://www.alphavantage.co/terms_of_service/
- **Coverage gaps:** Public API candidate, not open licensed source; calendar completeness and adjustment method need tests.

## A3 — Nasdaq Daily List

- **Category:** A. Equity market data
- **Url:** https://www.nasdaqtrader.com/Trader.aspx?id=dailylistpd
- **Coverage:** Nasdaq listed securities
- **Fields:** New listings; delistings; symbol/name changes; dividends
- **Extraction method:** Subscription data delivery
- **Update frequency:** Daily/events
- **Historical availability:** Historical access subject to product agreement
- **Authentication:** Subscription/login
- **Extraction outcome:** Product page reviewed; not downloaded
- **Commercial redistribution:** Contracted feed; confirm downstream redistribution and corporate-action entitlements.
- **Terms url:** https://www.nasdaqtrader.com/content/AdministrationSupport/Policy/USEquitiesandOptionsDataPolicies.pdf
- **Coverage gaps:** Not a free open-data source; global corporate actions need more exchanges/vendors.

## B1 — SEC EDGAR Company Facts and submissions

- **Category:** B. Company financial fundamentals
- **Url:** https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- **Coverage:** US SEC reporting issuers, including qualifying foreign filers
- **Fields:** CIK; entity name; taxonomy/tag; unit; value; period start/end; form; accession; filed date; fiscal year/period
- **Extraction method:** JSON REST; nightly bulk files for scale
- **Update frequency:** As filings are processed; bulk nightly
- **Historical availability:** XBRL coverage commonly from 2009; varies by issuer and concept
- **Authentication:** No API key; identify automated user agent and follow SEC fair access
- **Extraction outcome:** Docs reviewed; exploratory Apple endpoint returned HTTP 200, but no archived B pipeline is included
- **Commercial redistribution:** SEC states public filings and government-created content are reusable. Keep provenance; check separately licensed identifiers/third-party material.
- **Terms url:** https://www.sec.gov/about/webmaster-frequently-asked-questions
- **Coverage gaps:** Not standardized global financial statements. Restatements, extension tags and fiscal calendars require mapping; ratios are derived.

## B2 — SEC 13F and insider ownership filings

- **Category:** B. Company financial fundamentals
- **Url:** https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- **Coverage:** US-reporting institutional managers and insiders
- **Fields:** 13F manager/holding/share count/value/report period; Forms 3/4/5 owner/transaction date/shares/price/code
- **Extraction method:** EDGAR indexes and filing XML
- **Update frequency:** Filing/event-driven; 13F holdings lag the report date
- **Historical availability:** EDGAR archive depth varies; structured format availability varies
- **Authentication:** No API key; descriptive User-Agent; at most 10 requests/sec across machines
- **Extraction outcome:** Documentation reviewed; no filing extraction implemented
- **Commercial redistribution:** Filing content reusable per SEC policy; licensed identifiers need separate assessment. Do not infer holdings freshness from download time.
- **Terms url:** https://www.sec.gov/about/webmaster-frequently-asked-questions
- **Coverage gaps:** 13F does not represent every institution or position; filing corrections must be retained.

## C1 — SEC Form N-PORT data sets

- **Category:** C. ETF data
- **Url:** https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets
- **Coverage:** Covered US registered funds, including ETFs; not ETF-only
- **Fields:** Fund/series identifiers; reporting period; portfolio securities; values; exposures; available reported fund metrics
- **Extraction method:** Quarterly ZIP files of tabular structured data; filing XML alternative
- **Update frequency:** Quarterly bulk publication of public filing information
- **Historical availability:** Public archive starts October 2019
- **Authentication:** No API key; SEC fair-access rules
- **Extraction outcome:** Official archive reviewed; large ZIPs not downloaded
- **Commercial redistribution:** SEC reuse policy applies to filing content; assess proprietary identifiers separately.
- **Terms url:** https://www.sec.gov/about/webmaster-frequently-asked-questions
- **Coverage gaps:** Not daily holdings, daily NAV, global ETF master or market prices. Identify ETFs and honor filing/release lag.

## C2 — Alpha Vantage ETF profile and holdings

- **Category:** C. ETF data
- **Url:** https://www.alphavantage.co/documentation/#etf-profile
- **Coverage:** Provider-supported ETFs; global completeness unverified
- **Fields:** ETF profile; expense ratio; assets; holdings; sector allocations; related price endpoints
- **Extraction method:** JSON API
- **Update frequency:** Provider-dependent; holdings as-of dates must be inspected
- **Historical availability:** Snapshot/history coverage endpoint-dependent; not confirmed
- **Authentication:** API key and plan entitlement
- **Extraction outcome:** Documentation reviewed; data not extracted
- **Commercial redistribution:** Commercial redistribution requires written agreement; not assumed from public API access.
- **Terms url:** https://www.alphavantage.co/terms_of_service/
- **Coverage gaps:** Premium/discount requires matching-date NAV and exchange close; split/currency alignment needed.

## D1 — ECB euro foreign exchange reference rates

- **Category:** D. Forex and currency data
- **Url:** https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml
- **Coverage:** EUR against published currencies; additions/removals over time
- **Fields:** Observation date; quoted currency; units of quoted currency per EUR
- **Extraction method:** XML file; normalized into daily observations
- **Update frequency:** Working days, normally around 16:00 CET, excluding TARGET closures
- **Historical availability:** EUR reference history since 1999; varies by currency
- **Authentication:** None
- **Extraction outcome:** HTTP 200 archived; working pipeline and normalized samples included
- **Commercial redistribution:** Reuse subject to ECB attribution, accurate presentation, marking modifications and informing paying users that original information is freely available. Information rates, not execution quotes.
- **Terms url:** https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html
- **Coverage gaps:** No intraday OHLCV, executable spread or exchange holiday API. Cross-rates are derived.

## E1 — Coinbase Exchange public market data

- **Category:** E. Cryptocurrency data
- **Url:** https://docs.cdp.coinbase.com/exchange/introduction/welcome
- **Coverage:** Products traded on Coinbase Exchange only
- **Fields:** Product/base/quote; trades; prices; volume; order book; timestamped candles
- **Extraction method:** Public REST and WebSocket
- **Update frequency:** Streaming/event-driven; REST snapshots
- **Historical availability:** Product and endpoint dependent; historical candles require bounded windows
- **Authentication:** Public market endpoints do not require trading authentication
- **Extraction outcome:** Docs/terms reviewed; no ingestion performed
- **Commercial redistribution:** Current market-data terms prohibit external redistribution and derived works without prior express written consent.
- **Terms url:** https://www.coinbase.com/legal/market_data
- **Coverage gaps:** No universal crypto price or global supply/market cap; venue and geographic availability vary.

## E2 — CoinGecko market aggregates

- **Category:** E. Cryptocurrency data
- **Url:** https://www.coingecko.com/en/api
- **Coverage:** Provider-tracked global crypto assets and venues
- **Fields:** Asset ID; price; market cap; volume; exchange/ticker reference; historical market series
- **Extraction method:** REST API
- **Update frequency:** Plan and endpoint dependent
- **Historical availability:** Plan, endpoint and asset dependent
- **Authentication:** Demo/paid API key as applicable
- **Extraction outcome:** Official API and terms pages reviewed; no keyed extraction
- **Commercial redistribution:** Incorporating data in a product differs from reselling API access. Redistribution/syndication requires an executed agreement.
- **Terms url:** https://www.coingecko.com/en/api_terms
- **Coverage gaps:** Market cap depends on supply methodology; retain provider-specific methodology and timestamps.

## F1 — EIA Open Data

- **Category:** F. Commodities and precious metals
- **Url:** https://www.eia.gov/opendata/documentation.php
- **Coverage:** US and selected international energy data
- **Fields:** Period; product/process/area dimensions; price or volume; units; series metadata
- **Extraction method:** API v2 JSON; some bulk files
- **Update frequency:** Daily/weekly/monthly/annual depending on route
- **Historical availability:** Series-specific; inspect route metadata for start/end
- **Authentication:** Free registration/API key
- **Extraction outcome:** Official API, copyright and service terms reviewed; no key used
- **Commercial redistribution:** EIA describes government publications as public domain; check series for non-government content and comply with API terms.
- **Terms url:** https://www.eia.gov/about/copyrights_reuse.php
- **Coverage gaps:** Energy series only; no complete metals/agriculture/futures contracts universe.

## F2 — World Bank Pink Sheet

- **Category:** F. Commodities and precious metals
- **Url:** https://www.worldbank.org/en/research/commodity-markets
- **Coverage:** Global benchmark energy, metals and agricultural commodity series
- **Fields:** Commodity; month/year; average benchmark price; unit
- **Extraction method:** Monthly/annual Excel downloads
- **Update frequency:** Monthly
- **Historical availability:** Long monthly/annual history; exact start varies by series and workbook
- **Authentication:** None
- **Extraction outcome:** Official download page reviewed; workbook not extracted
- **Commercial redistribution:** World Bank dataset licence and any third-party exceptions must be checked at series level; preserve attribution.
- **Terms url:** https://data.worldbank.org/summary-terms-of-use
- **Coverage gaps:** Monthly benchmark averages are not exchange spot ticks or tradable futures settlements.

## G1 — US Treasury daily par yield curves

- **Category:** G. Bonds and fixed income
- **Url:** https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- **Coverage:** US sovereign nominal par curve maturities
- **Fields:** NEW_DATE; BC_nMONTH; BC_nYEAR; value in annual percent; missing maturity values
- **Extraction method:** XML by year/month; all-history feed paginated
- **Update frequency:** US business days
- **Historical availability:** Nominal par curve since 1990; individual tenors start later
- **Authentication:** None
- **Extraction outcome:** 2024 and 2025 XML returned HTTP 200; pipeline and archives included
- **Commercial redistribution:** Government-origin series is a relatively low-friction candidate; this project has not established a blanket worldwide redistribution licence. Confirm source-specific and jurisdictional rights before launch; no official endorsement.
- **Terms url:** https://www.usa.gov/government-copyright
- **Coverage gaps:** A fitted par curve, not security prices, a zero curve, bond total returns, coupons or credit ratings.

## G2 — Fiscal Data average Treasury interest rates

- **Category:** G. Bonds and fixed income
- **Url:** https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/
- **Coverage:** US Treasury security categories
- **Fields:** record_date; security_type_desc; security_desc; avg_interest_rate_amt
- **Extraction method:** REST JSON/CSV/XML; filters and pagination
- **Update frequency:** Monthly
- **Historical availability:** Dataset from 2001; verify per-series completeness
- **Authentication:** No API key
- **Extraction outcome:** Small exploratory API request returned HTTP 200; not part of the packaged three-pipeline evidence
- **Commercial redistribution:** Government-origin candidate; confirm exact dataset reuse terms and geographic scope before redistribution.
- **Terms url:** https://www.usa.gov/government-copyright
- **Coverage gaps:** Average interest cost by category is not a market yield or individual bond coupon.

## H1 — S&P Dow Jones Indices licensing

- **Category:** H. Indices and benchmarks
- **Url:** https://www.spglobal.com/spdji/en/about-us/data-index-licensing/
- **Coverage:** Provider equity, sector, fixed-income and commodity index families
- **Fields:** Contracted index values/returns; constituents/weights and reference metadata according to entitlement
- **Extraction method:** Licensed data service; public pages for discovery only
- **Update frequency:** Daily or intraday by contract
- **Historical availability:** Index and contract dependent
- **Authentication:** Commercial contract; credentials
- **Extraction outcome:** Official licensing page reviewed; no index data downloaded
- **Commercial redistribution:** Explicit index/data licence required; publicly visible values are not permission to sell an index API.
- **Terms url:** https://www.spglobal.com/spdji/en/about-us/data-index-licensing/
- **Coverage gaps:** No verified open global constituent/weight source; benchmark branding and use rights differ.

## I1 — World Bank Indicators API / WDI

- **Category:** I. Economic and macroeconomic data
- **Url:** https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
- **Coverage:** World economies; prototype uses IND/USA/GBR GDP growth
- **Fields:** Indicator ID; country ISO3; year; value; unit/metadata; source update date
- **Extraction method:** Paginated JSON API
- **Update frequency:** GDP annual observation frequency; releases/revisions follow source updates, not daily price ticks
- **Historical availability:** Many indicators span 50+ years; varies by country/indicator
- **Authentication:** No API key
- **Extraction outcome:** Real GDP-growth request returned HTTP 200; pipeline preserves source bytes and generates samples
- **Commercial redistribution:** WDI GDP-growth metadata identifies CC BY 4.0; attribute and mark normalization. Check metadata/licence for each additional indicator.
- **Terms url:** https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NY.GDP.MKTP.KD.ZG
- **Coverage gaps:** Prototype implements one indicator only. Inflation, unemployment, reserves, industrial production and calendars need additional sources/adapters.

## I2 — FRED and ALFRED

- **Category:** I. Economic and macroeconomic data
- **Url:** https://fred.stlouisfed.org/docs/api/fred/
- **Coverage:** US and international economic series from many underlying publishers
- **Fields:** Series ID; date; value; frequency; units; seasonal adjustment; vintage dates where available
- **Extraction method:** JSON/XML REST; per-series metadata
- **Update frequency:** Underlying series release schedule
- **Historical availability:** Series-specific; vintage availability also varies
- **Authentication:** Registered API key
- **Extraction outcome:** Official API terms reviewed; no API extraction
- **Commercial redistribution:** Rights vary by underlying series. Check copyright notes; a FRED key does not grant redistribution rights to every series.
- **Terms url:** https://fred.stlouisfed.org/docs/api/terms_of_use.html
- **Coverage gaps:** Source-level attribution, vintage semantics and calendar release times require explicit mapping.

## J1 — Computed analytics / TA-Lib candidate

- **Category:** J. Financial analytics APIs
- **Url:** https://ta-lib.org/
- **Coverage:** Only the assets/series for which licensed inputs are available
- **Fields:** RSI; MACD; moving averages; returns; volatility; drawdown; correlation; benchmark-relative performance
- **Extraction method:** Compute locally from validated input series; TA-Lib optional, not installed or used in this prototype
- **Update frequency:** On ingestion or request
- **Historical availability:** Limited by clean input history and indicator warm-up period
- **Authentication:** No source API key for local computations
- **Extraction outcome:** Library documentation reviewed; requested investment analytics not implemented; FX conversion demo included separately
- **Commercial redistribution:** TA-Lib software has BSD licensing; software permission does not grant market-data or derived-output redistribution rights.
- **Terms url:** https://ta-lib.github.io/
- **Coverage gaps:** Define adjusted/total-return input, return convention, calendar, warm-up, ddof and minimum overlap; no forward filling across missing prices by default.

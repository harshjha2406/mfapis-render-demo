"""Regenerate the readable catalogue and weighted ranking from research inputs."""
import json
from pathlib import Path

C = []


def source(id, category, name, url, coverage, fields, method, frequency, history, auth, outcome, rights, terms, gap):
    C.append(dict(id=id, category=category, name=name, url=url, coverage=coverage, fields=fields,
                  extraction_method=method, update_frequency=frequency, historical_availability=history,
                  authentication=auth, extraction_outcome=outcome, commercial_redistribution=rights,
                  terms_url=terms, coverage_gaps=gap, reviewed_on="2026-10-26"))


source("A1", "A. Equity market data", "Nasdaq symbol directory",
 "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs", "US Nasdaq and other US exchange listings",
 "Symbol; security name; market category; ETF flag; test issue; financial status", "Delimited files; field definitions on page",
 "Current trading-day snapshots", "Current master; archive snapshots yourself, not a historical delisting database",
 "No key for public directory", "Official documentation reviewed; file ingestion not implemented",
 "Public access established; commercial redistribution permission not established for the directory. Confirm in writing before sale.",
 "https://www.nasdaqtrader.com/trader.aspx?id=copydisclaimmain", "No OHLCV; no worldwide master; symbol changes need temporal identifiers.")
source("A2", "A. Equity market data", "Alpha Vantage equity and calendar endpoints",
 "https://www.alphavantage.co/documentation/", "Selected global securities; exact symbol and endpoint coverage require validation",
 "Daily date/open/high/low/close/volume; dividend/split; company overview; IPO/earnings calendar; gainers/losers",
 "JSON/CSV API", "Endpoint-dependent: daily, intraday or event-based", "Daily history advertised as 20+ years; plan and symbol dependent",
 "API key; endpoint/plan entitlements", "Documentation and terms reviewed; no authenticated extraction performed",
 "Default terms are personal/noncommercial; written commercial agreement required. A paid key alone is not resale permission.",
 "https://www.alphavantage.co/terms_of_service/", "Public API candidate, not open licensed source; calendar completeness and adjustment method need tests.")
source("A3", "A. Equity market data", "Nasdaq Daily List",
 "https://www.nasdaqtrader.com/Trader.aspx?id=dailylistpd", "Nasdaq listed securities",
 "New listings; delistings; symbol/name changes; dividends", "Subscription data delivery", "Daily/events",
 "Historical access subject to product agreement", "Subscription/login", "Product page reviewed; not downloaded",
 "Contracted feed; confirm downstream redistribution and corporate-action entitlements.",
 "https://www.nasdaqtrader.com/content/AdministrationSupport/Policy/USEquitiesandOptionsDataPolicies.pdf",
 "Not a free open-data source; global corporate actions need more exchanges/vendors.")
source("B1", "B. Company financial fundamentals", "SEC EDGAR Company Facts and submissions",
 "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "US SEC reporting issuers, including qualifying foreign filers",
 "CIK; entity name; taxonomy/tag; unit; value; period start/end; form; accession; filed date; fiscal year/period",
 "JSON REST; nightly bulk files for scale", "As filings are processed; bulk nightly", "XBRL coverage commonly from 2009; varies by issuer and concept",
 "No API key; identify automated user agent and follow SEC fair access", "Docs reviewed; exploratory Apple endpoint returned HTTP 200, but no archived B pipeline is included",
 "SEC states public filings and government-created content are reusable. Keep provenance; check separately licensed identifiers/third-party material.",
 "https://www.sec.gov/about/webmaster-frequently-asked-questions", "Not standardized global financial statements. Restatements, extension tags and fiscal calendars require mapping; ratios are derived.")
source("B2", "B. Company financial fundamentals", "SEC 13F and insider ownership filings",
 "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data", "US-reporting institutional managers and insiders",
 "13F manager/holding/share count/value/report period; Forms 3/4/5 owner/transaction date/shares/price/code",
 "EDGAR indexes and filing XML", "Filing/event-driven; 13F holdings lag the report date", "EDGAR archive depth varies; structured format availability varies",
 "No API key; descriptive User-Agent; at most 10 requests/sec across machines",
 "Documentation reviewed; no filing extraction implemented",
 "Filing content reusable per SEC policy; licensed identifiers need separate assessment. Do not infer holdings freshness from download time.",
 "https://www.sec.gov/about/webmaster-frequently-asked-questions", "13F does not represent every institution or position; filing corrections must be retained.")
source("C1", "C. ETF data", "SEC Form N-PORT data sets",
 "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets", "Covered US registered funds, including ETFs; not ETF-only",
 "Fund/series identifiers; reporting period; portfolio securities; values; exposures; available reported fund metrics",
 "Quarterly ZIP files of tabular structured data; filing XML alternative", "Quarterly bulk publication of public filing information",
 "Public archive starts October 2019", "No API key; SEC fair-access rules",
 "Official archive reviewed; large ZIPs not downloaded",
 "SEC reuse policy applies to filing content; assess proprietary identifiers separately.",
 "https://www.sec.gov/about/webmaster-frequently-asked-questions", "Not daily holdings, daily NAV, global ETF master or market prices. Identify ETFs and honor filing/release lag.")
source("C2", "C. ETF data", "Alpha Vantage ETF profile and holdings",
 "https://www.alphavantage.co/documentation/#etf-profile", "Provider-supported ETFs; global completeness unverified",
 "ETF profile; expense ratio; assets; holdings; sector allocations; related price endpoints",
 "JSON API", "Provider-dependent; holdings as-of dates must be inspected", "Snapshot/history coverage endpoint-dependent; not confirmed",
 "API key and plan entitlement", "Documentation reviewed; data not extracted",
 "Commercial redistribution requires written agreement; not assumed from public API access.",
 "https://www.alphavantage.co/terms_of_service/", "Premium/discount requires matching-date NAV and exchange close; split/currency alignment needed.")
source("D1", "D. Forex and currency data", "ECB euro foreign exchange reference rates",
 "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml", "EUR against published currencies; additions/removals over time",
 "Observation date; quoted currency; units of quoted currency per EUR", "XML file; normalized into daily observations",
 "Working days, normally around 16:00 CET, excluding TARGET closures", "EUR reference history since 1999; varies by currency",
 "None", "HTTP 200 archived; working pipeline and normalized samples included",
 "Reuse subject to ECB attribution, accurate presentation, marking modifications and informing paying users that original information is freely available. Information rates, not execution quotes.",
 "https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html",
 "No intraday OHLCV, executable spread or exchange holiday API. Cross-rates are derived.")
source("E1", "E. Cryptocurrency data", "Coinbase Exchange public market data",
 "https://docs.cdp.coinbase.com/exchange/introduction/welcome", "Products traded on Coinbase Exchange only",
 "Product/base/quote; trades; prices; volume; order book; timestamped candles", "Public REST and WebSocket",
 "Streaming/event-driven; REST snapshots", "Product and endpoint dependent; historical candles require bounded windows",
 "Public market endpoints do not require trading authentication", "Docs/terms reviewed; no ingestion performed",
 "Current market-data terms prohibit external redistribution and derived works without prior express written consent.",
 "https://www.coinbase.com/legal/market_data", "No universal crypto price or global supply/market cap; venue and geographic availability vary.")
source("E2", "E. Cryptocurrency data", "CoinGecko market aggregates",
 "https://www.coingecko.com/en/api", "Provider-tracked global crypto assets and venues",
 "Asset ID; price; market cap; volume; exchange/ticker reference; historical market series",
 "REST API", "Plan and endpoint dependent", "Plan, endpoint and asset dependent",
 "Demo/paid API key as applicable", "Official API and terms pages reviewed; no keyed extraction",
 "Incorporating data in a product differs from reselling API access. Redistribution/syndication requires an executed agreement.",
 "https://www.coingecko.com/en/api_terms", "Market cap depends on supply methodology; retain provider-specific methodology and timestamps.")
source("F1", "F. Commodities and precious metals", "EIA Open Data",
 "https://www.eia.gov/opendata/documentation.php", "US and selected international energy data",
 "Period; product/process/area dimensions; price or volume; units; series metadata", "API v2 JSON; some bulk files",
 "Daily/weekly/monthly/annual depending on route", "Series-specific; inspect route metadata for start/end",
 "Free registration/API key", "Official API, copyright and service terms reviewed; no key used",
 "EIA describes government publications as public domain; check series for non-government content and comply with API terms.",
 "https://www.eia.gov/about/copyrights_reuse.php", "Energy series only; no complete metals/agriculture/futures contracts universe.")
source("F2", "F. Commodities and precious metals", "World Bank Pink Sheet",
 "https://www.worldbank.org/en/research/commodity-markets", "Global benchmark energy, metals and agricultural commodity series",
 "Commodity; month/year; average benchmark price; unit", "Monthly/annual Excel downloads",
 "Monthly", "Long monthly/annual history; exact start varies by series and workbook",
 "None", "Official download page reviewed; workbook not extracted",
 "World Bank dataset licence and any third-party exceptions must be checked at series level; preserve attribution.",
 "https://data.worldbank.org/summary-terms-of-use", "Monthly benchmark averages are not exchange spot ticks or tradable futures settlements.")
source("G1", "G. Bonds and fixed income", "US Treasury daily par yield curves",
 "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed", "US sovereign nominal par curve maturities",
 "NEW_DATE; BC_nMONTH; BC_nYEAR; value in annual percent; missing maturity values",
 "XML by year/month; all-history feed paginated", "US business days", "Nominal par curve since 1990; individual tenors start later",
 "None", "2024 and 2025 XML returned HTTP 200; pipeline and archives included",
 "Government-origin series is a relatively low-friction candidate; this project has not established a blanket worldwide redistribution licence. Confirm source-specific and jurisdictional rights before launch; no official endorsement.",
 "https://www.usa.gov/government-copyright", "A fitted par curve, not security prices, a zero curve, bond total returns, coupons or credit ratings.")
source("G2", "G. Bonds and fixed income", "Fiscal Data average Treasury interest rates",
 "https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/", "US Treasury security categories",
 "record_date; security_type_desc; security_desc; avg_interest_rate_amt",
 "REST JSON/CSV/XML; filters and pagination", "Monthly", "Dataset from 2001; verify per-series completeness",
 "No API key", "Small exploratory API request returned HTTP 200; not part of the packaged three-pipeline evidence",
 "Government-origin candidate; confirm exact dataset reuse terms and geographic scope before redistribution.",
 "https://www.usa.gov/government-copyright", "Average interest cost by category is not a market yield or individual bond coupon.")
source("H1", "H. Indices and benchmarks", "S&P Dow Jones Indices licensing",
 "https://www.spglobal.com/spdji/en/about-us/data-index-licensing/", "Provider equity, sector, fixed-income and commodity index families",
 "Contracted index values/returns; constituents/weights and reference metadata according to entitlement",
 "Licensed data service; public pages for discovery only", "Daily or intraday by contract", "Index and contract dependent",
 "Commercial contract; credentials", "Official licensing page reviewed; no index data downloaded",
 "Explicit index/data licence required; publicly visible values are not permission to sell an index API.",
 "https://www.spglobal.com/spdji/en/about-us/data-index-licensing/", "No verified open global constituent/weight source; benchmark branding and use rights differ.")
source("I1", "I. Economic and macroeconomic data", "World Bank Indicators API / WDI",
 "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation", "World economies; prototype uses IND/USA/GBR GDP growth",
 "Indicator ID; country ISO3; year; value; unit/metadata; source update date",
 "Paginated JSON API", "GDP annual observation frequency; releases/revisions follow source updates, not daily price ticks",
 "Many indicators span 50+ years; varies by country/indicator", "No API key",
 "Real GDP-growth request returned HTTP 200; pipeline preserves source bytes and generates samples",
 "WDI GDP-growth metadata identifies CC BY 4.0; attribute and mark normalization. Check metadata/licence for each additional indicator.",
 "https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NY.GDP.MKTP.KD.ZG",
 "Prototype implements one indicator only. Inflation, unemployment, reserves, industrial production and calendars need additional sources/adapters.")
source("I2", "I. Economic and macroeconomic data", "FRED and ALFRED",
 "https://fred.stlouisfed.org/docs/api/fred/", "US and international economic series from many underlying publishers",
 "Series ID; date; value; frequency; units; seasonal adjustment; vintage dates where available",
 "JSON/XML REST; per-series metadata", "Underlying series release schedule", "Series-specific; vintage availability also varies",
 "Registered API key", "Official API terms reviewed; no API extraction",
 "Rights vary by underlying series. Check copyright notes; a FRED key does not grant redistribution rights to every series.",
 "https://fred.stlouisfed.org/docs/api/terms_of_use.html", "Source-level attribution, vintage semantics and calendar release times require explicit mapping.")
source("J1", "J. Financial analytics APIs", "Computed analytics / TA-Lib candidate",
 "https://ta-lib.org/", "Only the assets/series for which licensed inputs are available",
 "RSI; MACD; moving averages; returns; volatility; drawdown; correlation; benchmark-relative performance",
 "Compute locally from validated input series; TA-Lib optional, not installed or used in this prototype",
 "On ingestion or request", "Limited by clean input history and indicator warm-up period", "No source API key for local computations",
 "Library documentation reviewed; requested investment analytics not implemented; FX conversion demo included separately",
 "TA-Lib software has BSD licensing; software permission does not grant market-data or derived-output redistribution rights.",
 "https://ta-lib.github.io/", "Define adjusted/total-return input, return convention, calendar, warm-up, ddof and minimum overlap; no forward filling across missing prices by default.")

Path("source_catalogue.json").write_text(json.dumps(C, indent=2))
lines = ["# Source catalogue", "", "Reviewed 26 October 2026. `HTTP 200 archived` means an actual packaged data response. `Documentation reviewed` does not mean extraction or redistribution was verified. URLs below are official discovery/documentation/terms URLs; successful selected-source request URLs are in `data/http_evidence.jsonl`.", ""]
for r in C:
    lines += [f"## {r['id']} — {r['name']}", ""]
    for k,v in r.items():
        if k not in {"id","name","reviewed_on"}: lines.append(f"- **{k.replace('_',' ').capitalize()}:** {v}")
    lines.append("")
Path("SOURCES.md").write_text("\n".join(lines))

weights = dict(demand=20, availability=15, maintenance_ease=10, licensing=20, engineering_ease=10, differentiation=10, subscription=15)
inputs = [
 ("I", "Macroeconomics", [4,5,5,4,5,3,4], "Selected; expand beyond one indicator after demand validation"),
 ("D", "Daily reference FX", [4,5,5,4,5,2,4], "Selected; comply with ECB reuse disclosures"),
 ("G", "Sovereign yield curves", [4,5,4,4,4,4,4], "Selected; narrow US curve scope; rights review pending"),
 ("B", "Company fundamentals", [5,4,2,4,2,5,5], "Next-stage candidate; XBRL reconciliation and history are costly"),
 ("J", "Derived analytics", [4,4,3,3,3,2,4], "Bundle feature after input-rights and calculation validation"),
 ("F", "Monthly commodities", [3,4,4,3,4,3,3], "Selective series rights clearance required"),
 ("C", "ETF holdings", [4,3,2,3,2,4,4], "Lagged filings; IDs and fund mapping raise effort"),
 ("A", "Global equity market data", [5,3,2,1,2,2,5], "No-go for resale until exchange/vendor agreements"),
 ("E", "Cryptocurrency", [4,4,2,1,3,2,4], "No-go for public venue redistribution without permission"),
 ("H", "Commercial indices", [4,2,2,1,2,2,4], "No-go without index licences"),
]
matrix=[]
for cat,label,scores,decision in inputs:
    d=dict(category=cat,label=label,**dict(zip(weights,scores)),decision=decision)
    d['score_100']=sum(d[k]*w for k,w in weights.items())/5
    matrix.append(d)
matrix.sort(key=lambda x:x['score_100'],reverse=True)
Path("opportunity_matrix.json").write_text(json.dumps({"weights_percent":weights,"scale":"1=weak/unfavorable, 5=strong/favorable. Low costs/complexity score high. Analyst judgments, not measured customer demand. Licence clearance is a hard launch gate regardless of total.","ranking":matrix},indent=2))
cols=['category','label',*weights,'score_100']
out=['# Product opportunity matrix','', 'Scores are analyst hypotheses, not market research. Scale: 1–5, with 5 favorable. Low maintenance cost and low engineering complexity score high. Licence clearance is a separate mandatory launch gate. Narrow sovereign curves are assessed for G, not all global bonds.','', 'Weights: '+', '.join(f'{k} {v}%' for k,v in weights.items()),'', '| '+' | '.join(cols)+' |', '| '+' | '.join(['---']*len(cols))+' |']
out += ['| '+' | '.join(str(r[c]) for c in cols)+' |' for r in matrix]
out += ['', 'Formula: score out of 100 = sum(weight × rating) / 5.', '', '## Decisions', '']
out += [f"- **{r['label']} ({r['score_100']:.0f}):** {r['decision']}" for r in matrix]
out += ['', 'The top three scores are close: a one-point licensing change shifts a score by four points. Treat the shortlist as a feasibility choice and validate customer demand before final investment.']
Path("OPPORTUNITY_MATRIX.md").write_text('\n'.join(out))

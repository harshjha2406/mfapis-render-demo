# MFAPIs — Your own FX quote API

**Current architecture:** MFAPIs controls its FastAPI quote ingestion endpoint, source validation, PostgreSQL quote storage, history, bid/ask conversion, inversion and basic cross-rate calculation. No runtime dependency on third-party forex rate APIs such as Twelve Data or Massive. A real-time feed must still **supply actual market observations**, with appropriate redisplay and API distribution rights. See [OWN_FX_API.md](OWN_FX_API.md) and [QUICK_START_MAC.md](QUICK_START_MAC.md).

**Not yet connected:** This upgrade does not provide real market prices by itself. The live widget will show an unavailable state until an authorized feed sends fresh quotes; ECB daily historical reference conversion remains separately available. **Never label daily rates or synthetic test values as live.**

---

## Other MFAPIs datasets

- European Central Bank: historical daily currency reference rates (not live market quotes).
- U.S. Treasury: daily yield data.
- World Bank: macroeconomic indicators.

## Installation and developer workflow

- [QUICK_START_MAC.md](QUICK_START_MAC.md) — Mac setup and GitHub/Render deployment.
- [OWN_FX_API.md](OWN_FX_API.md) — architecture, endpoint catalog, auth and feed integration.
- [START_HERE.md](START_HERE.md) — original data-pipeline instructions.
- [REPORT.md](REPORT.md), [SOURCES.md](SOURCES.md), [OPPORTUNITY_MATRIX.md](OPPORTUNITY_MATRIX.md) — research documentation.
- [VERIFICATION.md](VERIFICATION.md), [evidence/](evidence/) — execution verification.

Historical data ingestion and research work are preserved. Previous vendor-specific upgrade documents, if still present, are **archival only**.

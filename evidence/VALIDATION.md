# Local Validation — MFAPIs

Environment: macOS, Python 3.13.6, PostgreSQL 16 via Docker.

## Results
- PostgreSQL replay completed successfully.
- Automated tests: 21 passed, 1 warning, no skipped tests.
- Live pipeline reported success.
- Observations endpoint: HTTP 200 for World Bank / IND.
- Currency conversion endpoint: HTTP 200 for USD to INR.
- Conversion date: 2025-12-31.
- 100 USD converted to approximately 8,986.94 INR.

## PostgreSQL record counts
- ECB: 15,330
- Treasury: 6,487
- World Bank: 6
- Total: 21,823

## Saved evidence
- fx_conversion.json
- worldbank_india.json
- database_counts.txt

These results document the local demonstration.
Commercial redistribution permissions still require source-specific review.

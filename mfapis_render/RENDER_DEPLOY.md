# Current release: MFAPIs 0.3.0

Start with [UPGRADE.md](UPGRADE.md) to update the existing Render service with latest FX and source refresh. Read [LIVE_UPGRADE_NOTES.md](LIVE_UPGRADE_NOTES.md) for changes, validation and remaining production work.

The material below describes the earlier historical-data deployment and is retained for context; its no-refresh statements no longer describe release0.3.0.

---

# Deploy the MFAPIs dashboard on Render

This package adds a browser dashboard to the existing FastAPI project. It has not yet been deployed to your account.
The instructions were checked against Render's official documentation on 27 October 2026.

## What Girish will see

Open the deployed website's home page `/`, not just `/docs`:

- World Bank GDP growth: select India, the US or the UK.
- ECB exchange-rate history: select a currency pair and dates.
- US Treasury yield history: select a maturity and dates.
- Charts, paginated tables, CSV downloads, raw JSON and source attribution.
- An exact-date currency converter. For example: USD to INR, 100, 2025-12-31.

The records are real downloaded observations, initially covering 2024–2025. They are not synthetic or a real-time feed.
Each dataset displays its observation coverage and source retrieval date. Opening the dashboard queries the deployed database; it does not fetch the providers again.

## 1. Download and extract this deployment package

Keep your working local assignment folder. Extract this ZIP into a separate folder.
Inside the extracted `mfapis_render` folder, you should see `render.yaml`, `requirements.txt`,
`seed_manifest.json`, `mfapis/`, `data/` and `exports/`.

Do not copy your local `.env`, `.venv` or SQLite database files into this deployment folder.

## 2. Put the deployment files on GitHub

1. Sign in to https://github.com/ or create an account.
2. Create a repository named `mfapis-render-demo`. A private repository is fine.
3. Initialize it with a README so the upload controls are easy to find.
4. Choose **Add file → Upload files**.
5. Drag the CONTENTS of the extracted `mfapis_render` folder into the upload area.
   Upload the files and folders, not the ZIP and not the outer `mfapis_render` folder.
6. Commit the upload.
7. On the repository's first page, confirm `render.yaml` and `requirements.txt` are visible at the root.

The complete package is fewer than 100 files, and each file is below GitHub's 25 MiB browser-upload limit.
The archived data must be included: it supplies the initial database contents and provenance.
If the browser leaves out hidden files, the Render deployment still gets its Python version from `render.yaml`.
Keep `.gitignore` when using Git locally. Never commit real database credentials.

## 3. Deploy with a Render Blueprint

1. Sign in at https://dashboard.render.com/.
2. Choose **New → Blueprint**.
3. Connect GitHub and authorize access to your `mfapis-render-demo` repository.
4. Select that repository and its `main` branch.
5. Use `render.yaml` as the Blueprint path.
6. Review the resources before deploying:

| Resource | Configuration |
|---|---|
| Web service | `mfapis-harsh-demo`, Python, Free, Singapore |
| Database | `mfapis-harsh-db`, PostgreSQL 16, Free, Singapore |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -m mfapis.bootstrap && python -m uvicorn mfapis.api:app --host 0.0.0.0 --port $PORT` |
| Health check | `/healthz` |
| Python version | `3.13.6` |

7. Deploy the Blueprint. Button wording may vary, such as **Deploy Blueprint** or **Apply**.

The YAML requests free plans explicitly. Check the displayed resources and pricing before confirming.
If the workspace already has a free PostgreSQL database, Render may not permit another. Do not delete an existing database or select a paid plan without checking its purpose and cost.

Render injects the database's internal connection string into the web service's `DATABASE_URL`.
The code selects the installed psycopg 3 driver automatically. You do not need to copy your Mac password.
The database accepts private-network connections only; this does not prevent the web service from accessing it in the same region.

## 4. Wait for the first deployment

The build installs the Python dependencies. The start command then:

1. Creates the database tables.
2. Verifies the exported snapshot hash and referenced raw-response hashes.
3. Loads 21,823 observations, revision snapshots and checkpoints in one transaction into an EMPTY database.
4. Starts FastAPI on Render's assigned port.

Look for `seed_success` and `Application startup complete` in the web service logs.
On later restarts, `seed_skipped` is normal: existing observations are retained rather than overwritten.
No database loading runs during the build phase, and no paid shell or pre-deploy hook is required.

The initial snapshot is your original normalized export. Its original retrieval timestamps remain unchanged.
The archive's later Mac ETL evidence describes a separate capture; this deployment does not relabel either capture as newly downloaded.

## 5. Test the actual public link

Open the exact `https://...onrender.com` URL shown on your web service page.
Do not assume its hostname from the suggested service name; Render can choose a different available hostname.

Check:

- The home page shows **21,823** total observations and a populated GDP chart.
- Each of the three dataset tabs loads real values.
- Changing country/currency/maturity and clicking Apply filters changes the data.
- USD → INR, amount 100, date 2025-12-31 returns approximately 8,986.94 INR.
- CSV download and View JSON work.
- `/healthz` returns `{"status":"ok"}`.
- `/docs` opens the API documentation.

Use a private browser window or another device to confirm the public URL works without your Render login.
Only after these checks, send the actual homepage URL to Girish. Your laptop can then be closed; Render hosts the app.

## Free-plan limitations relevant to the demonstration

Render's free web service sleeps after 15 minutes without inbound traffic and can take about one minute to wake.
A free Render PostgreSQL database expires 30 days after creation. For a link that must remain available beyond that period,
review paid database options or another persistent PostgreSQL host before expiry. Do not promise permanent uptime on this plan.

The web filesystem is ephemeral. PostgreSQL retains the normalized data across web-service restarts while the database remains active.
Bundled source files are redeployed from Git. New files written by future ingestion jobs would need durable storage to survive restarts.

## Fresh provider updates

The existing ingestion commands remain available. No scheduler or public write endpoint was added.
This release is a historical-data demonstration. Do not describe it as automatically current or real-time.
If fresh observations are needed, run an authorized ingestion job with the deployed database connection and durable raw storage;
plan that separately from this initial deployment. Never expose a database URL or an unprotected ingestion action in the browser.

## Local preview in the extracted folder (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DATABASE_URL=sqlite:///render_preview.db
python -m mfapis.bootstrap
python -m uvicorn mfapis.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ . This optional preview uses SQLite; the supplied Render Blueprint uses PostgreSQL.
Use a different port if your earlier local API is still running. The preview does not change your Docker PostgreSQL data.

## Troubleshooting

| Symptom | Check |
|---|---|
| Render cannot find `render.yaml` | Upload the extracted folder's contents at the repository root. |
| `No module named mfapis` | The `mfapis` folder must sit beside `requirements.txt`; avoid an extra outer folder. |
| Build fails | Read the first relevant error in the build log. Share the error text, not environment secrets. |
| Database unavailable | Confirm the database is active, same region, and `DATABASE_URL` is linked by the Blueprint. |
| Startup checksum failure | Upload the unchanged `exports/observations.jsonl`, `seed_manifest.json` and `data/raw` files. |
| First visit takes a while | Allow the free service to wake, then reload. |
| Conversion returns no data | Try 2025-12-31; weekends, holidays or unavailable currencies do not silently carry forward. |
| More than one free database requested | Inspect existing resources before provisioning another; preserve existing data. |

## Official references

- https://render.com/docs/deploy-fastapi
- https://render.com/docs/blueprint-spec
- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/free
- https://render.com/docs/python-version
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository

The root README points to this guide. Original assignment reports and evidence remain included for context.

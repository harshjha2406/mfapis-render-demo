# Mac installation — MFAPIs-owned FX API

## 1. Install patch into your existing PUBLIC demo repo

Download `MFAPIs_Own_FX_API_Upgrade.zip` to Downloads, then in Terminal:

```bash
cd ~/Desktop/mfapis-render-demo-fix
git branch backup-before-own-api
unzip -o ~/Downloads/MFAPIs_Own_FX_API_Upgrade.zip -d .
source ~/Desktop/mfapis-review-venv/bin/activate
python -m pytest -q tests/
```

The ZIP is a **patch**, not the full ETL archive. Unzip it into the root of your repo; it does not replace your research files, existing README, or source snapshots. Read `MFAPIS_CURRENT_FX_README.md` for the new project summary. The old README may still contain historical references to previous providers; those are no longer the active runtime.

## 2. Push to your Render-connected GitHub repo

```bash
git status --short
git add -A
git -c core.pager=cat diff --cached --check
git commit -m "Build MFAPIs-owned FX quote API and feed ingestion"
git push origin main
```

Your existing Render web service should deploy automatically if auto-deploy is enabled; otherwise select **Manual Deploy > Deploy latest commit** in the Render UI.

## 3. Configure private Render environment

Your Render service: https://dashboard.render.com/

- Add `MFAPIS_INGEST_KEY` with a strong random key (`openssl rand -hex 32`). **Do not share it with ChatGPT or GitHub.**
- Keep `FX_LIVE_DISPLAY_AUTHORIZED=false` until your market quote source and redistribution rights are verified.
- Set `FX_REFRESH_SECONDS=15` and `FX_MAX_QUOTE_AGE_SECONDS=120`.
- Delete unused old `TWELVE_DATA_API_KEY` and `MASSIVE_API_KEY` variables.
- Deploy/restart if necessary. **Until you connect an authorized real market quote source, the live converter will say unavailable. It will not make up a rate.**

## 4. Update Girish's PRIVATE repo, without changing its Git remote

```bash
cd ~/Desktop/global-funds-etl-harsh
git branch backup-before-own-api
unzip -o ~/Downloads/MFAPIs_Own_FX_API_Upgrade.zip -d .
source ~/Desktop/mfapis-review-venv/bin/activate
python -m pytest -q tests/
git add -A
git -c core.pager=cat diff --cached --check
git commit -m "Replace vendor rate API with MFAPIs-owned FX service"
git push origin main
```

**Do not push to the wrong repo or force push.** In each folder verify `git remote -v` before pushing. The original README is deliberately preserved. After the push, consider updating its FX section to link to `OWN_FX_API.md` and mark old vendor implementations historical. Do not overwrite Girish’s existing content without reviewing it.

For API endpoints, source requirements and the feed adapter interface, read `OWN_FX_API.md`.

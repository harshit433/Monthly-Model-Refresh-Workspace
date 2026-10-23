# Running the app

**You do not need Node.** The FastAPI backend serves the entire web UI at `/`
with no build step. The React app in `frontend/` is optional (dev-only, needs
Node). So "running the app" = running the Python backend. Pick the option that
fits your laptop.

On first open you choose **Environment → BMC → Model refresh**, then the
workspace loads your mapping and alignment.

---

## Option A — Databricks App (recommended; nothing to install locally)

Runs the backend inside your Databricks workspace, reading your tables directly.

1. **Get the code in the workspace.** Workspace → **Repos** → *Add Repo* →
   `https://github.com/harshit433/Monthly-Model-Refresh-Workspace.git`.
2. **Have a SQL warehouse** (Serverless is fine). Note its ID — the HTTP path is
   `/sql/1.0/warehouses/<ID>` (SQL Warehouse → *Connection details*).
3. **Edit `backend/app.yaml`** env values for your workspace:
   - `MMM_CATALOG_<ENV>` — the catalog/schema that holds `secondary_modelling_*`
     (include the env token however it really appears, e.g. a `_uat` suffix or a
     3-level `catalog.schema`).
   - `MMM_ADLS_BASE_<ENV>` — ADLS/DBFS base path for baselines + outputs.
   - `DATABRICKS_HTTP_PATH` — your warehouse's HTTP path.
   - `MMM_BASELINE_DIR` — a Workspace/Volume path for the baseline Excel files.
4. **Create the app.** Compute → **Apps** → *Create app* → point it at the
   `backend/` folder (the one with `app.yaml`). Databricks installs
   `requirements.txt` and runs `uvicorn mmm_refresh.api:app`.
5. **Grant access** to the app's *service principal*: `SELECT` on
   `<catalog>.secondary_modelling_*` and `CAN USE` on the warehouse.
   Authentication then happens automatically via the service principal (no token
   needed — `databricks-sdk` is in `requirements.txt`).
6. **Open the app URL**, pick Environment/BMC/Refresh, and work.

*To use a Personal Access Token instead of the service principal:* add a
Databricks **secret** and reference it as `DATABRICKS_TOKEN` in `app.yaml`
(`valueFrom`).

---

## Option B — your laptop (only if Python is allowed; still no Node)

```bash
git clone https://github.com/harshit433/Monthly-Model-Refresh-Workspace.git
cd Monthly-Model-Refresh-Workspace/backend
pip install -r requirements.txt

export MMM_LIVE=1
export DATABRICKS_SERVER_HOSTNAME=adb-XXXX.XX.azuredatabricks.net
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/XXXX
export DATABRICKS_TOKEN=dapiXXXX
export MMM_CATALOG_DEV=eki_refined_db
export MMM_ADLS_BASE_DEV=dbfs:/mnt/.../Users_MMM

python3 -m uvicorn mmm_refresh.api:app --port 8000
# open http://localhost:8000/
```

Needs network access from the laptop to the Databricks SQL warehouse.

---

## Option C — just try it (no Databricks, no config)

```bash
cd backend && pip install -r requirements.txt
python3 -m uvicorn mmm_refresh.api:app --port 8000     # MMM_LIVE unset -> demo data
# open http://localhost:8000/
```

---

## Optional: the React dev app (needs Node)

Only if you specifically want the Vite dev experience; the served UI is the same
app. See [`frontend/README.md`](frontend/README.md).

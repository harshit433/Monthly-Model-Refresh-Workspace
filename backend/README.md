# Monthly Model Refresh — backend

FastAPI + a pure Python engine that reproduces the Databricks "Monthly Model
Refresh" pipeline: map source variables into the processed space, align
(reconcile) against the processed/contribution tables in real time, and
decompose — with as much of the mapping automated as possible (token
similarity + baseline, numeric verification), no LLM.

## Layout (`mmm_refresh/`)

| module | role |
|---|---|
| `regions.py` | `RegionKey` tuple-region parsing; `RegionUniverse` expand/club set-logic |
| `tokens.py` | variable-name grammar parser + name similarity |
| `actions.py` | the 4 primitives (direct/rename/split/aggregate) + `Weight` (scalar/vector/rule) |
| `detect.py` | observed-ratio split classification (temporal/equal/proportional/additive/none) |
| `resolver.py` | baseline + token-similarity candidate ranking, confidence %, action classification |
| `transforms.py` | normalize → Hill → Adstock → Lag (with new-month continuation) |
| `decomp.py` | coefficient = contribution/transformed; weekly decomp |
| `engine.py` | reactive DAG: mapping → transforms → reconciliation / weekly deviation / decomp, incremental on edit |
| `datasource.py` | `DatabricksSource` (live Unity Catalog, env-parameterized) + `InMemorySource` (dev) |
| `baseline.py` | baseline mapping ↔ Excel (the only persisted state; ADLS in prod) |
| `config.py` | per-environment catalog + ADLS path (env chosen in the app) |
| `service.py` | session orchestration (load → resolve → engine) + JSON (de)serialization |
| `api.py` | FastAPI endpoints |

## Run

```bash
cd backend
python3 -m pytest -q                 # 43 tests
python3 -m uvicorn mmm_refresh.api:app --reload
# then open http://localhost:8000/  -> the mapping workspace UI
```

The default app serves a small in-memory demo dataset **and the mapping
workspace UI** (`static/index.html`) at `/`, so it runs end to end without a
cluster. The UI creates a session, loads auto-resolved proposals, lets you
filter / sort / rank by confidence, edit mappings (including manual splits:
membership / percentage / temporal), and commit — all against the live API.
For real use, build the service with `DatabricksSource` + `ExcelBaselineStore`
(ADLS) and pass it to `create_app(service=...)`.

## API

- `GET /environments`, `GET /refreshes?env=&bmc=`
- `POST /sessions` `{env, bmc, refresh}` → session summary (auto-resolved mapping + analysis)
- `GET /sessions/{id}` · `GET /sessions/{id}/analysis`
- `GET /sessions/{id}/mapping/{domain}` · `PATCH .../mapping/{domain}` `{proposals:[…]}` (incremental recompute)
- `POST /sessions/{id}/extend` → +1 month of new data (demo), continuation transforms → combined decomp
- `GET /sessions/{id}/insights` → contribution by variable / region / time + ROI (contribution ÷ spend)
- `POST /sessions/{id}/commit` → writes the verified mapping to the baseline store

The UI has a **Mapping** view and an **Insights** view (top-contributors, region
breakdown, contribution trend, ROI table, and an "Extend +1 month" button).

## Going live on Databricks

No code changes — set env vars (see `.env.example`) and run:

```bash
set -a && . ./.env && set +a
python3 -m uvicorn mmm_refresh.api:app
```

`MMM_LIVE=1` switches the app from the demo to `DatabricksSource` (reads
`<catalog>.secondary_modelling_*` per the chosen environment) + an Excel
baseline store. `get_env(name)` resolves each environment's catalog, ADLS base
and warehouse from `MMM_CATALOG_<ENV>` / `MMM_ADLS_BASE_<ENV>` /
`DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN`, so
the real per-env strings live in config, not code. Needs
`pip install databricks-sql-connector`.

## Notes

- Three mapping domains all resolve into the **processed** namespace:
  `raw_to_processed`, `processing_detail_to_processed`, `contribution_to_processed`.
- Reconciliation/alignment is **structure-sensitive**: because each variable is
  max-normalized independently, a constant split ratio is washed out and does
  not move the deviation chart. The chart catches wrong targets, changed
  shapes, and missing/extra variables — not constant ratios (those are set from
  the data/contribution or by the analyst).
- Remaining integration detail: confirm the exact env→catalog/ADLS strings in
  `config.py` against the real notebook paths.

# Monthly Model Refresh — Workspace

A rebuild of the MMM (Marketing Mix Modeling) "Monthly Model Refresh" pipeline —
originally an Azure Databricks notebook — as a web application
(Python/FastAPI backend + served UI, React/TypeScript to follow).

It reconciles model variables across domains into the processed namespace,
aligns the transformed output against the processed/contribution tables in real
time, decomposes contribution, and extends the model forward by one month —
with the mapping automated as far as possible (deterministic token similarity +
baseline + numeric verification, no LLM).

## Running it

**No Node required** — the backend serves the whole UI at `/`. See
**[DEPLOY.md](DEPLOY.md)** for the options: deploy as a **Databricks App**
(recommended, nothing to install), run `uvicorn` on your laptop, or try the demo.

## Contents

- **[`backend/`](backend/)** — the engine and API (FastAPI). See
  [`backend/README.md`](backend/README.md) for the module layout, how to run it
  (`uvicorn mmm_refresh.api:app`, then open `http://localhost:8000/` for the
  served mapping workspace + insights UI), the test suite, and how to go live on
  Databricks via `.env` (`backend/.env.example`).
- **[`frontend/`](frontend/)** — React + TypeScript (Vite) client for the same
  UI, componentized, talking to the API. See [`frontend/README.md`](frontend/README.md)
  (`npm install && npm run dev` → `http://localhost:5173`, with the backend on
  `:8000`). The backend also serves a self-contained version at `/`, so the
  React app is optional.

## Status

- Engine core (token parser, region model, action library, value-based split
  detection), resolver (baseline + token similarity + confidence), transforms
  (normalize → Hill → Adstock → Lag), decomposition, reactive alignment engine,
  Databricks/ADLS datasource + Excel baseline store, FastAPI API, and a served
  mapping-workspace + insights/ROI UI, and a React + TypeScript (Vite) front end.
  50 passing backend tests; frontend builds clean.
- Next: confirm live Databricks env/catalog/ADLS strings, real new-month CSV
  upload + combined-decomp export.

> The original notebook was supplied as phone photos; those image folders are
> intentionally excluded from the repo (they're reference material, not code).

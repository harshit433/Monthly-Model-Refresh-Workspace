# Monthly Model Refresh — Workspace

A rebuild of the MMM (Marketing Mix Modeling) "Monthly Model Refresh" pipeline —
originally an Azure Databricks notebook — as a web application
(Python/FastAPI backend + served UI, React/TypeScript to follow).

It reconciles model variables across domains into the processed namespace,
aligns the transformed output against the processed/contribution tables in real
time, decomposes contribution, and extends the model forward by one month —
with the mapping automated as far as possible (deterministic token similarity +
baseline + numeric verification, no LLM).

## Contents

- **[`backend/`](backend/)** — the engine and API. See [`backend/README.md`](backend/README.md)
  for the module layout, how to run it (`uvicorn mmm_refresh.api:app`, then open
  `http://localhost:8000/` for the mapping workspace + insights UI), the test
  suite, and how to go live on Databricks via `.env` (`backend/.env.example`).

## Status

- Engine core (token parser, region model, action library, value-based split
  detection), resolver (baseline + token similarity + confidence), transforms
  (normalize → Hill → Adstock → Lag), decomposition, reactive alignment engine,
  Databricks/ADLS datasource + Excel baseline store, FastAPI API, and a served
  mapping-workspace + insights/ROI UI. 50 passing tests.
- Next: confirm live Databricks env/catalog/ADLS strings, real new-month CSV
  upload + combined-decomp export, optional React/TS front end.

> The original notebook was supplied as phone photos; those image folders are
> intentionally excluded from the repo (they're reference material, not code).

# Monthly Model Refresh — frontend

React + TypeScript (Vite) client for the mapping-workspace + insights UI,
talking to the FastAPI backend.

## Run (dev)

```bash
# 1) start the backend (in ../backend)
cd ../backend && python3 -m uvicorn mmm_refresh.api:app --port 8000

# 2) start the frontend
cd ../frontend && npm install && npm run dev
# open http://localhost:5173
```

The Vite dev server proxies the API paths (`/sessions`, `/refreshes`, …) to
`http://localhost:8000`, so the app uses same-origin relative URLs. To point at
a different backend, set `VITE_API_BASE` (e.g. `VITE_API_BASE=https://api.example.com npm run dev`).

## Build

```bash
npm run build      # tsc -b && vite build  ->  dist/
npm run preview    # serve the built dist/
```

The built `dist/` can be served by any static host, or by FastAPI itself
(mount it) for a single-origin deployment.

## Layout (`src/`)

| file | role |
|---|---|
| `api.ts` | typed fetch client for the backend |
| `types.ts` | API response/request types |
| `App.tsx` | state + data loading + orchestration |
| `theme.ts` | light/dark theme hook |
| `util.ts` | humanize, confidence colour, dedup, sparkline math |
| `components/Header.tsx` | brand, Mapping/Insights toggle, BMC/refresh, commit |
| `components/SummaryTiles.tsx` | status counters (click to filter) |
| `components/Toolbar.tsx` | search, type chips, sort, review queue, accept-all |
| `components/MappingTable.tsx` | the grid, expandable split rows, sparklines |
| `components/SplitEditor.tsx` | right-drawer editor: membership / percentage / temporal |
| `components/Insights.tsx` | contribution by variable/region/time, ROI, extend |
| `components/Sparkline.tsx` | shared inline sparkline |

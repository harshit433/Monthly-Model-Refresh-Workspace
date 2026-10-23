"""FastAPI surface over the session service.

Runs offline by default against a demo in-memory source so the endpoints work
without a cluster; swap in `DatabricksSource` + `ExcelBaselineStore` (ADLS) for
real use via `create_app(service=...)`.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .baseline import NoBaselineStore
from .config import ENVIRONMENTS
from .datasource import InMemorySource, make_demo_data
from .service import SessionService

STATIC = Path(__file__).resolve().parent.parent / "static"


class CreateSession(BaseModel):
    env: str = "dev"
    bmc: str
    refresh: str


class EditMapping(BaseModel):
    proposals: list[dict]


def _demo_service() -> SessionService:
    src = InMemorySource()
    src.put("Brazil_Centrum", "2025 Q3 Refresh", make_demo_data())
    return SessionService(source_for_env=lambda env: src, baseline_store=NoBaselineStore())


def create_app(service: SessionService | None = None) -> FastAPI:
    svc = service or _demo_service()
    app = FastAPI(title="Monthly Model Refresh API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/")
    def index():
        f = STATIC / "index.html"
        if f.exists():
            return FileResponse(f)
        return JSONResponse({"message": "Monthly Model Refresh API. Frontend not built yet."})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/environments")
    def environments():
        return [{"name": e.name, "catalog": e.catalog} for e in ENVIRONMENTS.values()]

    @app.get("/bmcs")
    def bmcs(env: str):
        return {"bmcs": svc.list_bmcs(env)}

    @app.get("/refreshes")
    def refreshes(env: str, bmc: str):
        return {"refreshes": svc.list_refreshes(env, bmc)}

    @app.post("/sessions")
    def create_session(body: CreateSession):
        try:
            sess = svc.create(body.env, body.bmc, body.refresh)
        except KeyError as e:
            raise HTTPException(404, str(e))
        return sess.summary()

    @app.get("/sessions/{sid}")
    def get_session(sid: str):
        return _get(svc, sid).summary()

    @app.get("/sessions/{sid}/mapping/{domain}")
    def get_mapping(sid: str, domain: str):
        return _get(svc, sid).mapping_payload(domain)

    @app.patch("/sessions/{sid}/mapping/{domain}")
    def edit_mapping(sid: str, domain: str, body: EditMapping):
        return _get(svc, sid).edit(domain, body.proposals)

    @app.get("/sessions/{sid}/analysis")
    def analysis(sid: str):
        return _get(svc, sid).analysis()

    @app.post("/sessions/{sid}/extend")
    def extend(sid: str):
        from .datasource import make_demo_new_month
        sess = _get(svc, sid)
        new_dates, new_raw = make_demo_new_month()
        return sess.extend(new_dates, new_raw)

    @app.get("/sessions/{sid}/insights")
    def insights(sid: str):
        return _get(svc, sid).insights_payload()

    @app.post("/sessions/{sid}/commit")
    def commit(sid: str):
        return _get(svc, sid).commit()

    return app


def _get(svc: SessionService, sid: str):
    try:
        return svc.get(sid)
    except KeyError:
        raise HTTPException(404, f"session {sid} not found")


def create_app_from_env() -> FastAPI:
    """Live mode when MMM_LIVE is set: read source tables from Databricks per
    environment and store baselines as Excel under MMM_BASELINE_DIR. Otherwise
    the offline demo. No code changes needed to go live — only env vars."""
    import os
    if os.environ.get("MMM_LIVE", "").lower() in ("1", "true", "yes", "on"):
        from .baseline import ExcelBaselineStore
        from .config import get_env
        from .datasource import DatabricksSource
        token = os.environ.get("DATABRICKS_TOKEN", "")
        base_dir = os.environ.get("MMM_BASELINE_DIR", "./baselines")
        svc = SessionService(
            source_for_env=lambda e: DatabricksSource(get_env(e), token),
            baseline_store=ExcelBaselineStore(base_dir),
        )
        return create_app(svc)
    return create_app()


app = create_app_from_env()

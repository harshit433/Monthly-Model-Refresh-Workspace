import numpy as np
from fastapi.testclient import TestClient
from mmm_refresh.api import create_app
from mmm_refresh.baseline import ExcelBaselineStore
from mmm_refresh.datasource import InMemorySource, make_demo_data
from mmm_refresh.service import SessionService


def _service(baseline=None):
    src = InMemorySource()
    src.put("Brazil_Centrum", "2025 Q3 Refresh", make_demo_data())
    return SessionService(source_for_env=lambda env: src, baseline_store=baseline)


def test_service_create_resolves_and_aligns():
    svc = _service()
    sess = svc.create("dev", "Brazil_Centrum", "2025 Q3 Refresh")
    a = sess.analysis()
    # demo data is constructed to reconcile exactly
    assert all(r["aligned"] for r in a["reconciliation"])
    assert a["weekly_deviation"]["weeks_within_tol"] == a["weekly_deviation"]["weeks_total"]
    # the 'All' unattributed grps was auto-split across sub-brands
    raw_props = sess.proposals["raw_to_processed"]
    assert any(p.action == "split" for p in raw_props)


def test_api_end_to_end():
    client = TestClient(create_app(_service()))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/refreshes", params={"env": "dev", "bmc": "Brazil_Centrum"}).json()["refreshes"]

    r = client.post("/sessions", json={"env": "dev", "bmc": "Brazil_Centrum", "refresh": "2025 Q3 Refresh"})
    assert r.status_code == 200
    summary = r.json()
    sid = summary["id"]
    assert "raw_to_processed" in summary["domains"]

    m = client.get(f"/sessions/{sid}/mapping/raw_to_processed").json()
    assert m["proposals"]
    # enriched payload: targets carry series + active + category/kind
    split = next(p for p in m["proposals"] if p["action"] == "split")
    assert split["category"] in ("btl", "dummy") and split["kind"] == "membership"
    assert any(t.get("series") is not None for t in split["targets"])

    # edit: deactivate an active split target (weight 0) -> breaks its alignment
    active = next(t for t in split["targets"] if t["percent"] == 100.0)
    active["weight"] = {"kind": "scalar", "value": 0.0}
    active["percent"] = 0.0
    edited = client.patch(f"/sessions/{sid}/mapping/raw_to_processed",
                          json={"proposals": m["proposals"]}).json()
    assert edited["changed_targets"]
    assert any(not r["aligned"] for r in edited["analysis"]["reconciliation"])


def test_api_commit_writes_baseline(tmp_path):
    store = ExcelBaselineStore(str(tmp_path))
    client = TestClient(create_app(_service(baseline=store)))
    r = client.post("/sessions", json={"env": "dev", "bmc": "Brazil_Centrum", "refresh": "2025 Q3 Refresh"})
    sid = r.json()["id"]
    out = client.post(f"/sessions/{sid}/commit").json()
    assert out["committed"]
    # baseline file now exists and reloads
    reloaded = store.load("Brazil_Centrum", "raw_to_processed")
    assert len(reloaded) >= 1


def test_session_not_found_is_404():
    client = TestClient(create_app(_service()))
    assert client.get("/sessions/nope").status_code == 404

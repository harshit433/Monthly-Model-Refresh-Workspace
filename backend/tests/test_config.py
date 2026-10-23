from fastapi.testclient import TestClient
from mmm_refresh.config import get_env


def test_env_overrides_from_vars(monkeypatch):
    monkeypatch.setenv("MMM_CATALOG_UAT", "maincat_uat.eki_refined_db")
    monkeypatch.setenv("MMM_ADLS_BASE_UAT", "abfss://mmm@y.dfs.core.windows.net/M")
    monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "adb-1.azuredatabricks.net")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
    e = get_env("uat")
    assert e.catalog == "maincat_uat.eki_refined_db"
    assert e.table("raw_data") == "maincat_uat.eki_refined_db.secondary_modelling_raw_data"
    assert e.adls_base.startswith("abfss://")
    assert e.server_hostname == "adb-1.azuredatabricks.net"
    assert e.http_path == "/sql/1.0/warehouses/abc"
    assert e.baseline_path("Brazil_Centrum", "raw_to_processed").endswith(
        "/Brazil_Centrum/baselines/raw_to_processed.xlsx")


def test_default_env_without_overrides(monkeypatch):
    for k in ("MMM_CATALOG", "MMM_CATALOG_DEV", "MMM_ADLS_BASE", "MMM_ADLS_BASE_DEV"):
        monkeypatch.delenv(k, raising=False)
    e = get_env("dev")
    assert e.catalog == "eki_refined_db"
    assert e.table("contribution") == "eki_refined_db.secondary_modelling_contribution"


def test_app_defaults_to_demo(monkeypatch):
    monkeypatch.delenv("MMM_LIVE", raising=False)
    from mmm_refresh.api import create_app_from_env
    c = TestClient(create_app_from_env())
    assert c.get("/health").json()["status"] == "ok"
    r = c.post("/sessions", json={"env": "dev", "bmc": "Brazil_Centrum", "refresh": "2025 Q3 Refresh"})
    assert r.status_code == 200

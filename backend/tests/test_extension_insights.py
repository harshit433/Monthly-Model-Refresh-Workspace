from fastapi.testclient import TestClient
from mmm_refresh.api import create_app
from mmm_refresh.datasource import InMemorySource, make_demo_data, make_demo_new_month
from mmm_refresh.insights import invest_name
from mmm_refresh.service import SessionService


def _svc():
    s = InMemorySource()
    s.put("Brazil_Centrum", "2025 Q3 Refresh", make_demo_data())
    return SessionService(source_for_env=lambda e: s)


def test_invest_pairing():
    assert invest_name("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps") == \
        "media__tv__all-plac_otv_all-camp__sub-brand-access_invest"
    assert invest_name("sales__market__all-benefit__base__sales-units") is None


def test_extend_appends_new_month():
    sess = _svc().create("dev", "Brazil_Centrum", "2025 Q3 Refresh")
    nd, nr = make_demo_new_month()
    out = sess.extend(nd, nr)
    assert out["historical_weeks"] == 8 and out["new_weeks"] == 4 and out["combined_weeks"] == 12
    assert out["overlap"] == []
    assert sess.combined and len(sess.combined["dates"]) == 12
    # every combined series is historical(8) + new(4)
    for ser in sess.combined["decomp"].values():
        assert len(ser) == 12


def test_insights_historical_then_combined():
    sess = _svc().create("dev", "Brazil_Centrum", "2025 Q3 Refresh")
    ins0 = sess.insights_payload()
    assert ins0["scope"] == "historical" and len(ins0["trend"]["values"]) == 8
    sess.extend(*make_demo_new_month())
    ins = sess.insights_payload()
    assert ins["scope"] == "combined" and len(ins["trend"]["values"]) == 12
    assert ins["by_variable"] and ins["by_region"]
    # ROI computed for the activity var whose paired invest exists
    assert any("roi" in r for r in ins["by_variable"])
    # region shares sum to ~100%
    assert abs(sum(r["pct"] for r in ins["by_region"]) - 100.0) < 0.1


def test_api_extend_and_insights():
    client = TestClient(create_app(_svc()))
    sid = client.post("/sessions", json={"env": "dev", "bmc": "Brazil_Centrum",
                                          "refresh": "2025 Q3 Refresh"}).json()["id"]
    ex = client.post(f"/sessions/{sid}/extend").json()
    assert ex["combined_weeks"] == 12 and ex["overlap"] == []
    ins = client.get(f"/sessions/{sid}/insights").json()
    assert ins["scope"] == "combined"
    assert ins["by_variable"] and ins["total"] != 0

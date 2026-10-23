import numpy as np
from mmm_refresh.actions import TemporalBreakpoint, Weight
from mmm_refresh.baseline import ExcelBaselineStore, proposals_to_rows, rows_to_proposals
from mmm_refresh.regions import RegionKey
from mmm_refresh.resolver import MappingProposal, TargetRef


def _rk(s):
    return RegionKey.parse(s)


def sample_proposals():
    return [
        MappingProposal(sources=[("sales__u", _rk("('Access',)"))], action="direct",
                        targets=[TargetRef("sales__u", _rk("('Access',)"), Weight.scalar(1.0), 100.0)]),
        MappingProposal(sources=[("btl__unattr", _rk("('All',)"))], action="split",
                        targets=[
                            TargetRef("btl__unattr", _rk("('Access',)"), Weight.scalar(0.6), 60.0),
                            TargetRef("btl__unattr", _rk("('Multivitaminicos',)"), Weight.scalar(0.4), 40.0),
                        ]),
        MappingProposal(sources=[("m__x", _rk("('Access',)")), ("m__y", _rk("('Access',)"))],
                        action="aggregate",
                        targets=[TargetRef("m__z", _rk("('Access',)"), Weight.scalar(1.0), 100.0)]),
        MappingProposal(sources=[("dummy__inf", _rk("('Select',)"))], action="split",
                        targets=[
                            TargetRef("camp", _rk("('Select',)"),
                                      Weight.rule(TemporalBreakpoint("2025-05-01", "after")), 100.0),
                        ]),
    ]


def test_rows_roundtrip_preserves_actions_and_weights():
    props = sample_proposals()
    back = rows_to_proposals(proposals_to_rows(props))
    actions = sorted(p.action for p in back)
    assert actions == ["aggregate", "direct", "split", "split"]
    split = next(p for p in back if p.action == "split" and p.sources[0][0] == "btl__unattr")
    assert sorted(t.percent for t in split.targets) == [40.0, 60.0]
    agg = next(p for p in back if p.action == "aggregate")
    assert len(agg.sources) == 2
    rule_split = next(p for p in back if p.sources[0][0] == "dummy__inf")
    assert rule_split.targets[0].weight.kind == "rule"
    assert rule_split.targets[0].weight.value.breakpoint == "2025-05-01"


def test_excel_store_save_and_load(tmp_path):
    store = ExcelBaselineStore(str(tmp_path))
    store.save("Brazil_Centrum", "raw_to_processed", sample_proposals())
    loaded = store.load("Brazil_Centrum", "raw_to_processed")
    assert len(loaded) == 4
    bd = store.baseline_dict("Brazil_Centrum", "raw_to_processed")
    assert ("sales__u", _rk("('Access',)")) in bd


def test_missing_baseline_is_empty(tmp_path):
    store = ExcelBaselineStore(str(tmp_path))
    assert store.load("Nope", "raw_to_processed") == []
    assert store.baseline_dict("Nope", "raw_to_processed") == {}

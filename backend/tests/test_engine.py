import numpy as np
from mmm_refresh.actions import Weight
from mmm_refresh.engine import ReactiveEngine
from mmm_refresh.regions import RegionKey
from mmm_refresh.resolver import MappingProposal, TargetRef
from mmm_refresh.transforms import TransformParams, transform_series


def _rk(s):
    return RegionKey.parse(s)


def build_engine(split_w=(0.6, 0.4)):
    dates = ["2025-01-06", "2025-01-13", "2025-01-20", "2025-01-27"]
    raw = {
        ("media__x_grps", _rk("('All',)")): np.array([1., 2., 3., 4.]),
        ("sales__y_units", _rk("('Access',)")): np.array([10., 10., 10., 10.]),
    }
    params = {
        ("media__x_grps", _rk("('Access',)")): TransformParams(K=0.5, S=2.0, max_val=1.0, adstock_rate=30.0, lag_value=1),
        ("media__x_grps", _rk("('Multivitaminicos',)")): TransformParams(K=0.5, S=2.0, max_val=1.0, adstock_rate=30.0, lag_value=1),
    }
    proposals = [
        MappingProposal(
            sources=[("media__x_grps", _rk("('All',)"))], action="split",
            targets=[
                TargetRef("media__x_grps", _rk("('Access',)"), Weight.scalar(split_w[0]), split_w[0] * 100),
                TargetRef("media__x_grps", _rk("('Multivitaminicos',)"), Weight.scalar(split_w[1]), split_w[1] * 100),
            ],
        ),
        MappingProposal(
            sources=[("sales__y_units", _rk("('Access',)"))], action="direct",
            targets=[TargetRef("sales__y_units", _rk("('Access',)"), Weight.scalar(1.0), 100.0)],
        ),
    ]
    # processed = exactly what the mapping+transforms should reproduce
    processed = {}
    for tkey, w in [(("media__x_grps", _rk("('Access',)")), 0.6),
                    (("media__x_grps", _rk("('Multivitaminicos',)")), 0.4)]:
        processed[tkey] = transform_series(raw[("media__x_grps", _rk("('All',)"))] * w, params[tkey])
    processed[("sales__y_units", _rk("('Access',)"))] = transform_series(raw[("sales__y_units", _rk("('Access',)"))], None)
    contribution = {k: 100.0 for k in processed}
    return dates, raw, processed, contribution, params, proposals


def test_engine_reconciles_when_mapping_matches():
    dates, raw, processed, contribution, params, proposals = build_engine()
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)
    recon = eng.reconciliation()
    assert all(r.aligned for r in recon.values())
    assert np.allclose(eng.weekly_deviation(), 0, atol=1e-9)
    ua = eng.unaligned()
    assert ua["mismatch"] == [] and ua["raw_only"] == [] and ua["processed_only"] == []


def test_engine_decomp_reconciles_to_contribution():
    dates, raw, processed, contribution, params, proposals = build_engine()
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)
    from mmm_refresh.decomp import verify_decomp
    for tkey, dec in eng.decomp().items():
        ok, diff = verify_decomp(dec, contribution[tkey])
        assert ok, (tkey, diff)


def test_incremental_edit_recomputes_only_affected_targets():
    dates, raw, processed, contribution, params, proposals = build_engine()
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)

    # edit the split 0.6/0.4 -> 0.5/0.5: only the two media targets recompute
    edited = [
        MappingProposal(
            sources=[("media__x_grps", _rk("('All',)"))], action="split",
            targets=[
                TargetRef("media__x_grps", _rk("('Access',)"), Weight.scalar(0.5), 50.0),
                TargetRef("media__x_grps", _rk("('Multivitaminicos',)"), Weight.scalar(0.5), 50.0),
            ],
        ),
        proposals[1],
    ]
    delta = eng.apply_mapping(edited)
    changed = set(delta.changed_targets)
    assert ("media__x_grps", _rk("('Access',)")) in changed
    assert ("media__x_grps", _rk("('Multivitaminicos',)")) in changed
    assert ("sales__y_units", _rk("('Access',)")) not in changed   # untouched


def test_constant_split_ratio_is_washed_out_by_normalization():
    # a constant scalar is divided back out by per-variable max-normalization,
    # so changing 0.6/0.4 -> 0.5/0.5 does NOT move reconciliation. Constant
    # ratios are correct-by-construction (read from processed), not validated here.
    dates, raw, processed, contribution, params, proposals = build_engine()
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)
    edited = [
        MappingProposal(
            sources=[("media__x_grps", _rk("('All',)"))], action="split",
            targets=[
                TargetRef("media__x_grps", _rk("('Access',)"), Weight.scalar(0.5), 50.0),
                TargetRef("media__x_grps", _rk("('Multivitaminicos',)"), Weight.scalar(0.5), 50.0),
            ],
        ),
        proposals[1],
    ]
    delta = eng.apply_mapping(edited)
    assert all(r.aligned for r in eng.reconciliation().values())
    assert np.allclose(delta.weekly_deviation, 0, atol=1e-9)


def test_structural_edit_breaks_alignment():
    # a per-week mask changes the normalised SHAPE -> reconciliation detects it
    dates, raw, processed, contribution, params, proposals = build_engine()
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)
    edited = [
        MappingProposal(
            sources=[("media__x_grps", _rk("('All',)"))], action="split",
            targets=[
                TargetRef("media__x_grps", _rk("('Access',)"), Weight.vector([1., 1., 0., 0.]), 50.0),
                TargetRef("media__x_grps", _rk("('Multivitaminicos',)"), Weight.vector([0., 0., 1., 1.]), 50.0),
            ],
        ),
        proposals[1],
    ]
    delta = eng.apply_mapping(edited)
    recon = eng.reconciliation()
    assert not recon[("media__x_grps", _rk("('Access',)"))].aligned      # shape changed
    assert recon[("sales__y_units", _rk("('Access',)"))].aligned         # untouched
    assert not np.allclose(delta.weekly_deviation, 0)


def test_unaligned_reports_set_differences():
    dates, raw, processed, contribution, params, proposals = build_engine()
    # add a processed variable with no mapping -> processed_only
    processed[("sales__orphan", _rk("('Others',)"))] = np.array([1., 1., 1., 1.])
    eng = ReactiveEngine(dates, raw, processed, contribution, params, proposals)
    ua = eng.unaligned()
    assert ("sales__orphan", _rk("('Others',)")) in ua["processed_only"]

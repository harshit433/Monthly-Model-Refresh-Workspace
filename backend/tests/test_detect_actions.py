import numpy as np
from mmm_refresh.actions import TemporalBreakpoint, Weight, aggregate, direct, split
from mmm_refresh.detect import classify_children


# --- detection ---------------------------------------------------------------

def test_temporal_one_hot_split():
    parent = np.array([1., 2., 3., 4.])
    children = {"c1": np.array([1., 2., 0., 0.]), "c2": np.array([0., 0., 3., 4.])}
    r = classify_children(parent, children)
    assert r.kind == "temporal" and r.is_one_hot and r.reconciles
    wmap = {c.key: c.weight for c in r.children}
    assert np.allclose(wmap["c1"], [1, 1, 0, 0])
    assert np.allclose(wmap["c2"], [0, 0, 1, 1])


def test_membership_split_three_active_one_zero():
    # a source split into 4 regions; only 3 carry (equal) numbers, 1 is zero
    parent = np.array([5., 5., 5.])
    children = {
        "a": np.array([5., 5., 5.]), "b": np.array([5., 5., 5.]),
        "c": np.array([5., 5., 5.]), "d": np.array([0., 0., 0.]),
    }
    r = classify_children(parent, children)
    assert r.kind == "membership" and r.reconciles
    w = {c.key: c for c in r.children}
    assert w["a"].active and w["b"].active and w["c"].active and not w["d"].active
    assert np.allclose(w["a"].weight, 1) and np.allclose(w["d"].weight, 0)
    assert w["a"].percent == 100.0 and w["d"].percent == 0.0
    assert sorted(r.active_keys) == ["a", "b", "c"]


def test_all_equal_is_membership():
    parent = np.array([4., 4.])
    children = {"a": np.array([4., 4.]), "b": np.array([4., 4.])}
    r = classify_children(parent, children)
    assert r.kind == "membership"
    assert all(np.allclose(c.weight, 1) for c in r.children)


def test_unequal_active_values_flagged_as_varying():
    parent = np.array([10., 10.])
    children = {"a": np.array([6., 6.]), "b": np.array([4., 4.])}   # active but not equal
    r = classify_children(parent, children)
    assert r.kind == "varying" and not r.reconciles


# --- action library ----------------------------------------------------------

def test_split_then_aggregate_is_identity():
    src = np.array([5., 6., 7., 8.])
    w = [Weight.scalar(0.6), Weight.scalar(0.4)]
    parts = split(src, w)
    assert np.allclose(aggregate(parts), src)


def test_split_with_one_hot_masks():
    src = np.array([1., 2., 3., 4.])
    parts = split(src, [Weight.vector([1, 1, 0, 0]), Weight.vector([0, 0, 1, 1])])
    assert np.allclose(parts[0], [1, 2, 0, 0])
    assert np.allclose(parts[1], [0, 0, 3, 4])


def test_temporal_rule_projects_forward():
    # historical weeks + one NEW month week; breakpoint mid-history
    dates = ["2025-01-06", "2025-02-03", "2025-05-05", "2025-10-06"]
    src = np.array([10., 10., 10., 10.])
    before = Weight.rule(TemporalBreakpoint("2025-05-01", side="before"))
    after = Weight.rule(TemporalBreakpoint("2025-05-01", side="after"))
    parts = split(src, [before, after], dates=dates)
    assert np.allclose(parts[0], [10, 10, 0, 0])   # inf regime
    assert np.allclose(parts[1], [0, 0, 10, 10])   # sup regime incl. the new month
    assert np.allclose(aggregate(parts), src)


def test_direct_copies():
    src = np.array([1., 2.])
    out = direct(src)
    out[0] = 99.
    assert src[0] == 1.

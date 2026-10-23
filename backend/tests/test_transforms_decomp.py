import numpy as np
from mmm_refresh.transforms import (
    TransformParams, adstock, hill, lag, normalize, transform_series,
)
from mmm_refresh.decomp import coefficient, decompose, verify_decomp


def test_normalize_to_unit_range():
    normed, rmax = normalize(np.array([0., 5., 10.]))
    assert rmax == 10.0
    assert np.allclose(normed, [0, 0.5, 1.0])
    z, zmax = normalize(np.array([0., 0., 0.]))
    assert zmax == 0.0 and np.allclose(z, 0)


def test_hill_bounded_and_zero_at_zero():
    x = np.array([0., 0.25, 0.5, 1.0])
    y = hill(x, K=0.5, S=2.0, max_val=1.0)
    assert y[0] == 0.0
    assert np.all((y >= 0) & (y <= 1))
    assert np.all(np.diff(y) >= 0)  # monotonic increasing


def test_adstock_recursion_and_seed():
    d = np.array([1., 0., 0.])
    a = adstock(d, rate=50.0)                 # 1, 0.5, 0.25
    assert np.allclose(a, [1., 0.5, 0.25])
    a2 = adstock(np.array([0., 0.]), rate=50.0, seed=4.0)   # 2, 1
    assert np.allclose(a2, [2., 1.])


def test_lag_shift_and_continuation():
    a = np.array([1., 2., 3., 4.])
    assert np.allclose(lag(a, 0), a)
    assert np.allclose(lag(a, 2), [1., 1., 1., 2.])         # pad with first value
    assert np.allclose(lag(a, 2, hist_tail=np.array([8., 9.])), [8., 9., 1., 2.])


def test_pipeline_passthrough_is_just_normalize():
    s = np.array([2., 4., 8.])
    out = transform_series(s, None)
    assert np.allclose(out, [0.25, 0.5, 1.0])


def test_decomp_reconciles_to_contribution_total():
    lagged = np.array([0.2, 0.5, 1.0, 0.3])
    transformed_total = float(np.sum(lagged))
    contribution_total = 123.4
    coef = coefficient(transformed_total, contribution_total)
    dec = decompose(lagged, coef)
    ok, diff = verify_decomp(dec, contribution_total)
    assert ok and diff < 1e-6


def test_coefficient_zero_when_no_signal():
    assert coefficient(0.0, 50.0) == 0.0

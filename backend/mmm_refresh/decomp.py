"""Contribution decomposition.

Per (var, region):
    coefficient = contribution_total / transformed_total   (0 if denom 0)
    decomp[week] = lagged[week] * coefficient

where transformed_total = Σ lagged over the historical window and
contribution_total = Σ contribution_non_indexed from the contribution table.
The coefficient is back-calculated so the weekly decomposition sums back to the
known contribution total (verified to a 0.001 tolerance).
"""
from __future__ import annotations

import numpy as np

_EPS = 1e-12
DECOMP_TOL = 1e-3


def coefficient(transformed_total: float, contribution_total: float) -> float:
    if abs(transformed_total) <= _EPS:
        return 0.0
    return contribution_total / transformed_total


def decompose(lagged: np.ndarray, coef: float) -> np.ndarray:
    return np.asarray(lagged, dtype=float) * coef


def verify_decomp(decomp_series: np.ndarray, contribution_total: float,
                  tol: float = DECOMP_TOL) -> tuple[bool, float]:
    total = float(np.sum(decomp_series))
    diff = abs(total - contribution_total)
    return diff <= tol, diff

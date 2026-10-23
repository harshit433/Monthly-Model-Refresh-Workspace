"""MMM transformation pipeline: normalize -> Hill -> Adstock -> Lag.

Parameters are fitted on *normalised* data and come from the processing-details
table (value2..value6 in the notebook): K (half-saturation), S (slope),
max_val (max raw value at fit time), adstock_rate (carry-over %), lag_value
(weeks). A variable without a given parameter passes that stage through
unchanged, so non-media variables are simply normalised.

The adstock seed and lag history-tail let a *new month* continue from the end
of history instead of restarting, so carry-over flows across the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EPS = 1e-12


@dataclass(frozen=True)
class TransformParams:
    K: float | None = None
    S: float | None = None
    max_val: float | None = None
    adstock_rate: float | None = None
    lag_value: int | None = None

    @property
    def has_hill(self) -> bool:
        return self.K is not None and self.S is not None and self.max_val is not None


def normalize(x: np.ndarray) -> tuple[np.ndarray, float]:
    x = np.asarray(x, dtype=float)
    row_max = float(np.max(np.abs(np.nan_to_num(x)))) if x.size else 0.0
    if row_max <= _EPS:
        return np.zeros_like(x), 0.0
    return x / row_max, row_max


def normalize_with(x: np.ndarray, row_max: float) -> np.ndarray:
    """Normalise by a GIVEN max (the historical max) — used for new-month data
    so it's scaled consistently with the fitted history."""
    x = np.asarray(x, dtype=float)
    if row_max <= _EPS:
        return np.zeros_like(x)
    return x / row_max


def hill(x: np.ndarray, K: float, S: float, max_val: float) -> np.ndarray:
    """Diminishing-returns saturation. x is normalised. x<=0 -> 0 (IFERROR)."""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    nz = x > _EPS
    out[nz] = 1.0 / (1.0 + ((K * max_val) / x[nz]) ** S)
    return out


def adstock(d: np.ndarray, rate: float, seed: float = 0.0) -> np.ndarray:
    """Geometric carry-over: a[i] = d[i] + a[i-1]*(rate/100). `seed` = a[-1] of history."""
    d = np.asarray(d, dtype=float)
    out = np.empty_like(d)
    prev = float(seed)
    decay = rate / 100.0
    for i in range(d.shape[0]):
        cur = d[i] + prev * decay
        out[i] = cur
        prev = cur
    return out


def lag(a: np.ndarray, lag_steps: int, hist_tail: np.ndarray | None = None) -> np.ndarray:
    """Shift right by lag_steps. Lead positions filled from hist_tail (new month)
    or the first value (historical), tail beyond the window dropped."""
    a = np.asarray(a, dtype=float)
    n = a.shape[0]
    steps = max(int(lag_steps), 0)
    if steps == 0 or n == 0:
        return a.copy()
    steps = min(steps, n)
    if hist_tail is not None and len(hist_tail) >= steps:
        lead = np.asarray(hist_tail, dtype=float)[-steps:]
    else:
        fill = float(a[0])
        lead = np.array([fill] * steps)
        if hist_tail is not None and len(hist_tail) > 0:
            tail = np.asarray(hist_tail, dtype=float)
            lead = np.concatenate([np.array([fill] * (steps - len(tail))), tail])[-steps:]
    return np.concatenate([lead, a[: n - steps]])[:n]


def transform_stages(
    series: np.ndarray,
    params: TransformParams | None = None,
    adstock_seed: float = 0.0,
    lag_hist_tail: np.ndarray | None = None,
    norm_max: float | None = None,
) -> dict:
    """Run the pipeline and return every stage, so the new-month extension can
    continue adstock/lag from the historical intermediates.

    `norm_max` overrides the normalisation max (pass the HISTORICAL max for a
    new month); otherwise the series' own max is used.
    """
    if norm_max is None:
        normed, row_max = normalize(series)
    else:
        normed, row_max = normalize_with(series, norm_max), norm_max
    diminished = normed
    if params is not None and params.has_hill:
        diminished = hill(diminished, params.K, params.S, params.max_val)
    adstocked = diminished
    if params is not None and params.adstock_rate is not None:
        adstocked = adstock(adstocked, params.adstock_rate, seed=adstock_seed)
    lagged = adstocked
    if params is not None and params.lag_value:
        lagged = lag(lagged, params.lag_value, hist_tail=lag_hist_tail)
    return {"normed": normed, "diminished": diminished, "adstocked": adstocked,
            "lagged": lagged, "row_max": row_max}


def transform_series(
    series: np.ndarray,
    params: TransformParams | None = None,
    adstock_seed: float = 0.0,
    lag_hist_tail: np.ndarray | None = None,
) -> np.ndarray:
    """normalize -> (hill) -> (adstock) -> (lag). Each optional stage passes
    through when its parameter is absent."""
    return transform_stages(series, params, adstock_seed, lag_hist_tail)["lagged"]

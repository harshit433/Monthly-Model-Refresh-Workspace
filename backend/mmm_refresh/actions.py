"""Action function library — the only code that touches data *values*.

Every mapping reduces to four primitives plus skip:

    direct      target = source                     (1:1, identity)
    rename      target = source, new name           (1:1, relabel)
    split       one source -> N targets             (weights sum to 1 on support)
    aggregate   N sources -> one target             (weighted sum)
    skip        source dropped (no target)

One-hot / temporal / region / dummy splits are all `split` with different
`Weight`s. Weights come in three forms so splits can be *projected forward*:

    scalar  a constant ratio (e.g. 0.5 equal split, 0.6 proportional)
    vector  a per-week ratio/mask (e.g. one-hot [1,1,0,0])
    rule    a generator (e.g. a dated breakpoint) that yields the mask for
            any week grid, so a NEW month lands in the correct regime.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence

import numpy as np


class WeightRule(Protocol):
    def mask(self, dates: Sequence[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class TemporalBreakpoint:
    """A dated regime: weight 1 on the active side of ``breakpoint``, else 0.

    side='after'  -> active on/after the breakpoint (the 'sup'/later regime)
    side='before' -> active strictly before the breakpoint (the 'inf' regime)
    A new month (after all historical breakpoints) therefore flows into the
    'after' child automatically.
    """

    breakpoint: str          # YYYY-MM-DD
    side: str = "after"      # 'after' | 'before'

    def mask(self, dates: Sequence[str]) -> np.ndarray:
        bp = date.fromisoformat(self.breakpoint)
        ds = [date.fromisoformat(str(d)[:10]) for d in dates]
        if self.side == "before":
            return np.array([1.0 if d < bp else 0.0 for d in ds])
        return np.array([1.0 if d >= bp else 0.0 for d in ds])


@dataclass(frozen=True)
class Weight:
    kind: str                 # 'scalar' | 'vector' | 'rule'
    value: object             # float | np.ndarray | WeightRule

    @classmethod
    def scalar(cls, v: float) -> "Weight":
        return cls("scalar", float(v))

    @classmethod
    def vector(cls, v) -> "Weight":
        return cls("vector", np.asarray(v, dtype=float))

    @classmethod
    def rule(cls, r: WeightRule) -> "Weight":
        return cls("rule", r)

    def resolve(self, n_weeks: int, dates: Sequence[str] | None = None) -> np.ndarray:
        if self.kind == "scalar":
            return np.full(n_weeks, float(self.value))
        if self.kind == "vector":
            v = np.asarray(self.value, dtype=float)
            if v.shape[0] != n_weeks:
                raise ValueError(f"weight vector length {v.shape[0]} != {n_weeks} weeks")
            return v
        if self.kind == "rule":
            if dates is None:
                raise ValueError("rule weights need the week `dates` to resolve")
            return np.asarray(self.value.mask(dates), dtype=float)
        raise ValueError(f"unknown weight kind {self.kind!r}")


# --- primitives --------------------------------------------------------------

def direct(src: np.ndarray) -> np.ndarray:
    return np.asarray(src, dtype=float).copy()


def rename(src: np.ndarray) -> np.ndarray:
    # value-identity; the new name lives on the mapping row, not the series
    return np.asarray(src, dtype=float).copy()


def split(
    src: np.ndarray,
    weights: Sequence[Weight],
    dates: Sequence[str] | None = None,
) -> list[np.ndarray]:
    src = np.asarray(src, dtype=float)
    n = src.shape[0]
    return [src * w.resolve(n, dates) for w in weights]


def aggregate(
    sources: Sequence[np.ndarray],
    weights: Sequence[Weight] | None = None,
    dates: Sequence[str] | None = None,
) -> np.ndarray:
    srcs = [np.asarray(s, dtype=float) for s in sources]
    if not srcs:
        raise ValueError("aggregate needs at least one source")
    n = srcs[0].shape[0]
    if weights is None:
        return np.sum(srcs, axis=0)
    if len(weights) != len(srcs):
        raise ValueError("one weight per source required")
    return np.sum([s * w.resolve(n, dates) for s, w in zip(srcs, weights)], axis=0)

"""Split detection by VALUE, not ratio.

The processed table already holds the split targets. To classify a split we
look only at the target (child) series among themselves — no ratios:

    inactive child   all-zero                 -> weight 0 (gets nothing)
    temporal split   active children have time-disjoint supports (one-hot)
                     -> each active child = source gated by its 0/1 mask
    membership       active children carry the SAME values
                     -> each active child = the source (weight 1); zeros out
    varying          active children are non-zero but NOT equal -> flagged for
                     review (unusual; engine reconciliation will show the gap)

Example: a source split into 4 regions where only 3 have numbers -> those 3 are
equal and active (weight 1), the 4th is all-zero (weight 0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable

import numpy as np

DEFAULT_TOL = 1e-3
_EPS = 1e-9


@dataclass
class ChildWeight:
    key: Hashable
    weight: np.ndarray       # per-week weight applied to the source (mask or 1s/0s)
    active: bool
    percent: float           # 100 if active, 0 if not


@dataclass
class SplitClassification:
    kind: str                # temporal | membership | varying | none
    children: list[ChildWeight] = field(default_factory=list)
    reconciles: bool = True   # clean structure (temporal/membership); varying/none -> review

    @property
    def is_one_hot(self) -> bool:
        return self.kind == "temporal"

    @property
    def active_keys(self) -> list:
        return [c.key for c in self.children if c.active]


def classify_children(parent, children: dict[Hashable, np.ndarray],
                      tol: float = DEFAULT_TOL) -> SplitClassification:
    """Classify a split from the child (target) values alone. `parent` is
    unused for the decision (kept for signature stability)."""
    keys = list(children)
    mats = {k: np.asarray(children[k], dtype=float) for k in keys}
    n = len(next(iter(mats.values()))) if mats else 0
    supports = {k: np.abs(mats[k]) > _EPS for k in keys}
    active = [k for k in keys if supports[k].any()]
    scale = max((float(np.max(np.abs(mats[k]))) for k in keys), default=1.0)
    atol = tol * max(scale, 1.0)

    def build(kind: str, weight_of) -> SplitClassification:
        children_cw = []
        for k in keys:
            is_active = k in active
            children_cw.append(ChildWeight(k, weight_of(k, is_active),
                                           is_active, 100.0 if is_active else 0.0))
        clean = kind in ("temporal", "membership")
        return SplitClassification(kind, children_cw, clean)

    if not active:
        return build("none", lambda k, a: np.zeros(n))

    # temporal / one-hot: active children have pairwise-disjoint supports
    if len(active) >= 2:
        stacked = np.stack([supports[k] for k in active])
        if bool(np.all(stacked.sum(axis=0) <= 1)):
            return build("temporal", lambda k, a: supports[k].astype(float) if a else np.zeros(n))

    # membership: active children all carry the same values -> replicate source
    first = mats[active[0]]
    equal = all(np.allclose(mats[k], first, atol=atol, rtol=tol) for k in active)
    kind = "membership" if equal else "varying"
    return build(kind, lambda k, a: np.ones(n) if a else np.zeros(n))

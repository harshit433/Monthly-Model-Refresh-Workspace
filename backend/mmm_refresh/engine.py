"""Reactive compute engine.

Holds the loaded source data for one (BMC, refresh) and the current mapping,
and derives everything downstream:

    raw --(mapping)--> mapped --(normalize->Hill->Adstock->Lag)--> transformed
    transformed vs processed  -> reconciliation + weekly deviation + unaligned
    transformed + contribution -> coefficient -> decomp

A mapping edit only recomputes the targets whose contributions actually
changed (`apply_mapping`), then the cheap global weekly-deviation. At ~700
var*region x ~104 weeks even a full rebuild is sub-second; the diff keeps the
UI's "what changed" precise.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import decomp as dcmp
from .actions import Weight
from .regions import RegionKey
from .resolver import MappingProposal
from .transforms import TransformParams, transform_series

VarRef = tuple[str, RegionKey]

_EPS = 1e-12


@dataclass
class Reconciliation:
    transformed_total: float
    processed_total: float
    pct_diff: float
    aligned: bool


@dataclass
class EngineDelta:
    changed_targets: list[VarRef] = field(default_factory=list)
    weekly_deviation: np.ndarray | None = None


def _weight_sig(w: Weight):
    if w.kind == "vector":
        return ("vector", tuple(np.asarray(w.value, float).tolist()))
    if w.kind == "rule":
        r = w.value
        return ("rule", getattr(r, "breakpoint", None), getattr(r, "side", None))
    return ("scalar", float(w.value))


class ReactiveEngine:
    def __init__(
        self,
        dates: list[str],
        raw_series: dict[VarRef, np.ndarray],
        processed_series: dict[VarRef, np.ndarray],
        contribution_totals: dict[VarRef, float] | None = None,
        params: dict[VarRef, TransformParams] | None = None,
        proposals: list[MappingProposal] | None = None,
        historical_mask: np.ndarray | None = None,
        pct_tol: float = 0.5,
    ):
        self.dates = list(dates)
        self.n = len(self.dates)
        self.raw = {self._key(k): np.asarray(v, float) for k, v in raw_series.items()}
        self.processed = {self._key(k): np.asarray(v, float) for k, v in processed_series.items()}
        self.contribution = {self._key(k): float(v) for k, v in (contribution_totals or {}).items()}
        self.params = {self._key(k): v for k, v in (params or {}).items()}
        self.proposals = list(proposals or [])
        self.hist = np.ones(self.n, bool) if historical_mask is None else np.asarray(historical_mask, bool)
        self.pct_tol = pct_tol
        self._contrib: dict[VarRef, list[tuple[VarRef, Weight]]] = {}
        self._mapped: dict[VarRef, np.ndarray] = {}
        self._transformed: dict[VarRef, np.ndarray] = {}
        self._build_index(self.proposals)
        self.recompute_targets(list(self._contrib))

    # -- keys ---------------------------------------------------------------

    @staticmethod
    def _key(k) -> VarRef:
        var, region = k
        return (var, RegionKey.parse(region))

    # -- index + compute ----------------------------------------------------

    def _build_index(self, proposals) -> None:
        idx: dict[VarRef, list[tuple[VarRef, Weight]]] = {}
        for p in proposals:
            if p.action == "unmapped" or not p.targets:
                continue
            if p.action == "aggregate":
                tkey = (p.targets[0].var, p.targets[0].region)
                for s in p.sources:
                    idx.setdefault(tkey, []).append((s, Weight.scalar(1.0)))
            else:  # direct / rename / split: one source, per-target weight
                s = p.sources[0]
                for t in p.targets:
                    idx.setdefault((t.var, t.region), []).append((s, t.weight))
        self._contrib = idx

    def _compute_mapped(self, tkey: VarRef) -> np.ndarray:
        total = np.zeros(self.n)
        for skey, w in self._contrib.get(tkey, []):
            src = self.raw.get(skey)
            if src is None:
                continue
            total = total + src * w.resolve(self.n, self.dates)
        return total

    def recompute_targets(self, keys) -> None:
        for tkey in keys:
            m = self._compute_mapped(tkey)
            self._mapped[tkey] = m
            self._transformed[tkey] = transform_series(m, self.params.get(tkey))

    # -- incremental edit ---------------------------------------------------

    def _signature(self, idx) -> dict[VarRef, frozenset]:
        return {t: frozenset((s, _weight_sig(w)) for s, w in contribs)
                for t, contribs in idx.items()}

    def apply_mapping(self, proposals: list[MappingProposal]) -> EngineDelta:
        old_sig = self._signature(self._contrib)
        self.proposals = list(proposals)
        self._build_index(self.proposals)
        new_sig = self._signature(self._contrib)
        changed = [t for t in set(old_sig) | set(new_sig) if old_sig.get(t) != new_sig.get(t)]
        for t in changed:
            if t not in self._contrib:          # target removed
                self._mapped.pop(t, None)
                self._transformed.pop(t, None)
        self.recompute_targets([t for t in changed if t in self._contrib])
        return EngineDelta(changed_targets=changed, weekly_deviation=self.weekly_deviation())

    # -- outputs ------------------------------------------------------------

    def mapped(self, tkey) -> np.ndarray:
        return self._mapped[self._key(tkey)]

    def transformed(self, tkey) -> np.ndarray:
        return self._transformed[self._key(tkey)]

    def reconciliation(self) -> dict[VarRef, Reconciliation]:
        out = {}
        for tkey, tseries in self._transformed.items():
            p = self.processed.get(tkey)
            if p is None:
                continue
            tt = float(np.sum(tseries[self.hist]))
            pt = float(np.sum(p[self.hist]))
            if abs(pt) <= _EPS:
                pct = 0.0 if abs(tt) <= _EPS else 100.0
            else:
                pct = (tt - pt) / abs(pt) * 100.0
            out[tkey] = Reconciliation(tt, pt, pct, abs(pct) <= self.pct_tol)
        return out

    def weekly_deviation(self) -> np.ndarray:
        if not self._transformed:
            return np.zeros(self.n)
        tsum = np.sum([s for s in self._transformed.values()], axis=0)
        common = [self.processed[k] for k in self._transformed if k in self.processed]
        psum = np.sum(common, axis=0) if common else np.zeros(self.n)
        dev = np.zeros(self.n)
        nz = np.abs(psum) > _EPS
        dev[nz] = (tsum[nz] - psum[nz]) / np.abs(psum[nz]) * 100.0
        return dev

    def unaligned(self) -> dict[str, list]:
        recon = self.reconciliation()
        mismatch = [(k, r.pct_diff) for k, r in recon.items() if not r.aligned]
        mapped_keys = set(self._transformed)
        processed_keys = set(self.processed)
        raw_only = sorted(mapped_keys - processed_keys)
        processed_only = sorted(processed_keys - mapped_keys)
        return {
            "mismatch": sorted(mismatch, key=lambda x: -abs(x[1])),
            "raw_only": raw_only,
            "processed_only": processed_only,
        }

    def coefficients(self) -> dict[VarRef, float]:
        out = {}
        for tkey, lagged in self._transformed.items():
            tt = float(np.sum(lagged[self.hist]))
            out[tkey] = dcmp.coefficient(tt, self.contribution.get(tkey, 0.0))
        return out

    def decomp(self) -> dict[VarRef, np.ndarray]:
        coefs = self.coefficients()
        return {tkey: dcmp.decompose(lagged, coefs[tkey])
                for tkey, lagged in self._transformed.items()}

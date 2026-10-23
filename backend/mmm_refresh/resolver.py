"""Mapping resolver — propose how each source variable maps into processed.

Pipeline per source variable:

    1. baseline     if a prior verified mapping exists and still reconciles,
                    reuse it (highest confidence).
    2. name+region  exact (name, region) in processed      -> Direct
                    same name, source region expands         -> Split (region)
                    same name, source region clubs           -> Aggregate
    3. token sim    name not in processed -> rank processed names by
                    `tokens.similarity`; a 1:1 series match -> Rename;
                    otherwise a candidate for Split / Aggregate.
    4. aggregate    a second pass (`resolve_all`) merges several sources that
                    sum to one target into a single Aggregate proposal.

Grouping/ranking uses names (similarity); the *ratios and the accept/reject*
come from numeric reconciliation against the processed data (`detect`).
Nothing here invents a number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import tokens as tk
from .actions import TemporalBreakpoint, Weight
from .detect import DEFAULT_TOL, SplitClassification, classify_children
from .regions import RegionKey, RegionRelation, RegionUniverse

SUGGEST = 0.92          # >= -> ready to accept
REVIEW = 0.60           # [REVIEW, SUGGEST) -> needs a human look
RENAME_SIM = 0.72       # token similarity floor to call something a rename
CANDIDATE_SIM = 0.35    # floor to keep a token candidate at all

_EPS = 1e-12

VarRef = tuple[str, RegionKey]


@dataclass
class TargetRef:
    var: str
    region: RegionKey
    weight: Weight
    percent: float


@dataclass
class MappingProposal:
    sources: list[VarRef]
    action: str                       # direct | rename | split | aggregate | unmapped
    targets: list[TargetRef] = field(default_factory=list)
    confidence: float = 0.0
    provenance: str = "token"         # baseline | numeric | token | manual
    status: str = "unmapped"          # suggested | review | unmapped | confirmed
    evidence: dict = field(default_factory=dict)
    detection: SplitClassification | None = None


def _status(conf: float) -> str:
    if conf >= SUGGEST:
        return "suggested"
    if conf >= REVIEW:
        return "review"
    return "unmapped"


def _recon_conf(residual: float) -> float:
    return max(0.0, 1.0 - min(residual, 1.0))


def _series_residual(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    scale = max(np.max(np.abs(a)), np.max(np.abs(b)), _EPS)
    return float(np.max(np.abs(a - b)) / scale)


class ProcessedIndex:
    """Lookup over the processed (target) variable universe."""

    def __init__(self, series: dict[VarRef, np.ndarray], universe: RegionUniverse):
        self.series: dict[tuple[str, str], np.ndarray] = {}
        self.by_name: dict[str, list[RegionKey]] = {}
        self.tokens: dict[str, tk.VarToken] = {}
        self.universe = universe
        for (var, region), s in series.items():
            rk = RegionKey.parse(region)
            self.series[(var, rk.canonical)] = np.asarray(s, float)
            self.by_name.setdefault(var, [])
            if rk not in self.by_name[var]:
                self.by_name[var].append(rk)
            self.tokens.setdefault(var, tk.parse_variable(var))

    def get(self, var: str, region: RegionKey) -> np.ndarray | None:
        return self.series.get((var, region.canonical))

    def ranked_candidates(self, token: tk.VarToken, limit: int = 5) -> list[tuple[str, float]]:
        scored = [(name, tk.similarity(token, t)) for name, t in self.tokens.items()]
        scored = [(n, s) for n, s in scored if s >= CANDIDATE_SIM]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


class Resolver:
    def __init__(
        self,
        processed: ProcessedIndex,
        dates: list[str] | None = None,
        baseline: dict[VarRef, MappingProposal] | None = None,
        tol: float = DEFAULT_TOL,
    ):
        self.p = processed
        self.dates = dates
        self.baseline = baseline or {}
        self.tol = tol

    # -- per source ---------------------------------------------------------

    def resolve_variable(self, var: str, region, series: np.ndarray) -> MappingProposal:
        rk = RegionKey.parse(region)
        series = np.asarray(series, float)
        token = tk.parse_variable(var)

        base = self._from_baseline(var, rk, series)
        if base is not None:
            return base

        # 2a. exact (name, region) -> Direct. An exact name+region match is
        # unambiguous; series values differ across the transform boundary, so
        # they must NOT penalise confidence.
        exact = self.p.get(var, rk)
        if exact is not None:
            return MappingProposal(
                sources=[(var, rk)], action="direct",
                targets=[TargetRef(var, rk, Weight.scalar(1.0), 100.0)],
                confidence=0.98, provenance="numeric", status=_status(0.98),
                evidence={"match": "exact name+region"},
            )

        # 2b. same name, different region(s) -> Split (expand) or Aggregate (club)
        if var in self.p.by_name:
            prop = self._same_name_region(var, rk, series, token)
            if prop is not None:
                return prop

        # 3. name differs -> token similarity
        return self._by_similarity(var, rk, series, token)

    def _from_baseline(self, var, rk, series) -> MappingProposal | None:
        bp = self.baseline.get((var, rk))
        if bp is None:
            return None
        # verify referenced targets still exist and still reconcile
        tgt_series, ok = [], True
        for t in bp.targets:
            s = self.p.get(t.var, t.region)
            if s is None:
                ok = False
                break
            tgt_series.append(s)
        if not ok:
            bp2 = MappingProposal(**{**bp.__dict__})
            bp2.confidence = 0.55
            bp2.provenance = "baseline"
            bp2.status = "review"
            bp2.evidence = {**bp.evidence, "baseline": "target no longer present"}
            return bp2
        # baseline rows were confirmed before; carry them with high confidence
        # (cross-space residuals are not meaningful here).
        return MappingProposal(
            sources=[(var, rk)], action=bp.action, targets=bp.targets,
            confidence=0.95, provenance="baseline", status=_status(0.95),
            evidence={"baseline": "carried from prior refresh"},
            detection=bp.detection,
        )

    def _reconstruct_residual(self, series, prop, tgt_series) -> float:
        if prop.action in ("direct", "rename") and tgt_series:
            return _series_residual(series, tgt_series[0])
        if prop.action == "split" and tgt_series:
            total = np.sum(tgt_series, axis=0)
            return _series_residual(series, total)
        return 0.0

    def _same_name_region(self, var, rk, series, token) -> MappingProposal | None:
        regions = [r for r in self.p.by_name[var] if r != rk]
        if not regions:
            return None
        relation = self.p.universe.relation(rk, regions)
        if relation not in (RegionRelation.EXPAND, RegionRelation.DISJOINT):
            return None
        children = {r: self.p.get(var, r) for r in regions}
        children = {r: s for r, s in children.items() if s is not None}
        # classify by the target VALUES: which regions are active (same values)
        # vs zero. No ratios.
        cls = classify_children(series, children, self.tol)
        targets = self._split_targets(var, cls, token)
        n_active = len(cls.active_keys)
        conf = 0.93 if cls.reconciles else 0.62
        return MappingProposal(
            sources=[(var, rk)], action="split", targets=targets,
            confidence=conf, provenance="numeric", status=_status(conf),
            evidence={"match": f"region {cls.kind}", "active_regions": n_active,
                      "total_regions": len(children)},
            detection=cls,
        )

    def _split_targets(self, var, cls: SplitClassification, token) -> list[TargetRef]:
        targets = []
        for cw in cls.children:
            rk = cw.key if isinstance(cw.key, RegionKey) else RegionKey.parse(cw.key)
            if cls.kind == "temporal" and token.temporal_date:
                side = "before" if token.temporal_kind == "inf" else "after"
                w = Weight.rule(TemporalBreakpoint(token.temporal_date, side))
            elif cls.kind == "temporal":
                w = Weight.vector(cw.weight)              # 0/1 time mask
            else:
                w = Weight.scalar(1.0 if cw.active else 0.0)  # replicate to active, zero inactive
            targets.append(TargetRef(var, rk, w, cw.percent))
        return targets

    def _by_similarity(self, var, rk, series, token) -> MappingProposal:
        cands = self.p.ranked_candidates(token)
        if not cands:
            return MappingProposal(sources=[(var, rk)], action="unmapped",
                                   confidence=0.0, provenance="token", status="unmapped",
                                   evidence={"match": "no candidate above floor"})
        best_name, best_sim = cands[0]
        # Rename: a same-region target confirmed by a near-perfect series match
        # (same measurement space) or by a strong name match. A cross-space
        # series residual must NOT penalise a name-confirmed rename.
        tgt = self.p.get(best_name, rk)
        resid = _series_residual(series, tgt) if tgt is not None else 1.0
        if tgt is not None and (best_sim >= RENAME_SIM or resid <= self.tol):
            conf = 0.97 if resid <= self.tol else round(0.55 + 0.3 * best_sim, 3)
            return MappingProposal(
                sources=[(var, rk)], action="rename",
                targets=[TargetRef(best_name, rk, Weight.scalar(1.0), 100.0)],
                confidence=conf, provenance="token", status=_status(conf),
                evidence={"match": "renamed", "similarity": round(best_sim, 3)},
            )
        # Otherwise a weak candidate: surface top target for review
        conf = min(REVIEW + 0.001, best_sim * 0.6)
        tgt_region = rk if self.p.get(best_name, rk) is not None else self.p.by_name[best_name][0]
        return MappingProposal(
            sources=[(var, rk)], action="rename",
            targets=[TargetRef(best_name, tgt_region, Weight.scalar(1.0), 100.0)],
            confidence=conf, provenance="token", status="review",
            evidence={"match": "weak candidate", "similarity": round(best_sim, 3),
                      "candidates": [(n, round(s, 3)) for n, s in cands]},
        )

    # -- orchestration ------------------------------------------------------

    def resolve_all(self, sources: dict[VarRef, np.ndarray]) -> list[MappingProposal]:
        proposals = [self.resolve_variable(v, r, s) for (v, r), s in sources.items()]
        return self._merge_aggregates(proposals, sources)

    def _merge_aggregates(self, proposals, sources) -> list[MappingProposal]:
        # group single-target rename/direct proposals by their target; if several
        # sources sum to that target, replace them with one Aggregate proposal.
        by_target: dict[tuple[str, str], list[MappingProposal]] = {}
        for p in proposals:
            if p.action in ("rename", "direct") and len(p.targets) == 1:
                t = p.targets[0]
                by_target.setdefault((t.var, t.region.canonical), []).append(p)

        merged, consumed = [], set()
        for (tvar, treg), group in by_target.items():
            if len(group) < 2:
                continue
            tgt_region = RegionKey.parse(treg)
            tgt = self.p.get(tvar, tgt_region)
            if tgt is None:
                continue
            src_series = [sources[p.sources[0]] for p in group]
            total = np.sum(src_series, axis=0)
            resid = _series_residual(total, tgt)
            if resid <= self.tol * 10:
                conf = _recon_conf(resid)
                merged.append(MappingProposal(
                    sources=[p.sources[0] for p in group], action="aggregate",
                    targets=[TargetRef(tvar, tgt_region, Weight.scalar(1.0), 100.0)],
                    confidence=conf, provenance="numeric", status=_status(conf),
                    evidence={"match": f"{len(group)} sources sum to target", "residual": resid},
                ))
                for p in group:
                    consumed.add(p.sources[0])

        out = [p for p in proposals if not (len(p.sources) == 1 and p.sources[0] in consumed)]
        out.extend(merged)
        return out

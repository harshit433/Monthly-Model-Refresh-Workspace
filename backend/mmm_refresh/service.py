"""Session orchestration: load -> resolve -> engine, plus JSON (de)serialization.

A session holds one (env, BMC, refresh): the loaded data, the proposed mapping
per domain (auto-resolved, baseline-first), and a ReactiveEngine driving the
raw->processed alignment loop. Edits re-apply the mapping incrementally;
commit writes the confirmed mapping back to the baseline store.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .actions import TemporalBreakpoint, Weight
from .baseline import NoBaselineStore
from .config import DOMAINS
from .datasource import LoadedData
from .engine import ReactiveEngine
from .extension import extend as extend_engine
from .insights import insights as compute_insights
from .regions import RegionKey, RegionUniverse
from .resolver import MappingProposal, ProcessedIndex, Resolver, TargetRef

# -- serialization ------------------------------------------------------------

def dump_weight(w: Weight) -> dict:
    if w.kind == "vector":
        return {"kind": "vector", "value": np.asarray(w.value, float).tolist()}
    if w.kind == "rule":
        return {"kind": "rule", "breakpoint": w.value.breakpoint, "side": w.value.side}
    return {"kind": "scalar", "value": float(w.value)}


def load_weight(d: dict) -> Weight:
    kind = d.get("kind", "scalar")
    if kind == "vector":
        return Weight.vector(d["value"])
    if kind == "rule":
        return Weight.rule(TemporalBreakpoint(d["breakpoint"], d.get("side", "after")))
    return Weight.scalar(float(d["value"]))


_CATEGORIES = ("media", "btl", "sales", "dummy", "constant")


def _category(var: str) -> str:
    head = var.split("__", 1)[0].split("_", 1)[0].lower()
    return head if head in _CATEGORIES else "other"


def dump_proposal(p: MappingProposal) -> dict:
    return {
        "sources": [{"var": v, "region": r.canonical} for v, r in p.sources],
        "source_var": p.sources[0][0] if p.sources else None,
        "source_region": p.sources[0][1].canonical if p.sources else None,
        "category": _category(p.sources[0][0]) if p.sources else "other",
        "action": p.action,
        "kind": p.detection.kind if p.detection else None,
        "targets": [{"var": t.var, "region": t.region.canonical,
                     "percent": t.percent, "weight": dump_weight(t.weight)} for t in p.targets],
        "confidence": round(p.confidence, 4),
        "provenance": p.provenance,
        "status": p.status,
        "evidence": p.evidence,
    }


def load_proposal(d: dict) -> MappingProposal:
    sources = [(s["var"], RegionKey.parse(s["region"])) for s in d["sources"]]
    targets = [TargetRef(t["var"], RegionKey.parse(t["region"]),
                         load_weight(t.get("weight", {"kind": "scalar", "value": 1.0})),
                         float(t.get("percent", 100.0))) for t in d.get("targets", [])]
    return MappingProposal(sources=sources, action=d["action"], targets=targets,
                           confidence=float(d.get("confidence", 1.0)),
                           provenance=d.get("provenance", "manual"),
                           status=d.get("status", "confirmed"), evidence=d.get("evidence", {}))


def _ref(key) -> dict:
    var, region = key
    rk = region if isinstance(region, RegionKey) else RegionKey.parse(region)
    return {"var": var, "region": rk.canonical}


# -- session ------------------------------------------------------------------

@dataclass
class MappingSession:
    id: str
    env: str
    bmc: str
    refresh: str
    dates: list[str]
    proposals: dict[str, list[MappingProposal]]
    engine: ReactiveEngine
    _baseline: object = field(default_factory=NoBaselineStore)
    combined: object = None   # {"dates":[...], "decomp":{VarRef: ndarray}} after extend

    def counts(self, domain: str) -> dict:
        props = self.proposals.get(domain, [])
        by_status, by_prov = {}, {}
        for p in props:
            by_status[p.status] = by_status.get(p.status, 0) + 1
            by_prov[p.provenance] = by_prov.get(p.provenance, 0) + 1
        return {"total": len(props), "by_status": by_status, "by_provenance": by_prov}

    def analysis(self) -> dict:
        recon = self.engine.reconciliation()
        dev = self.engine.weekly_deviation()
        ua = self.engine.unaligned()
        within = int(np.sum(np.abs(dev) <= self.engine.pct_tol))
        return {
            "reconciliation": [
                {**_ref(k), "transformed_total": round(r.transformed_total, 6),
                 "processed_total": round(r.processed_total, 6),
                 "pct_diff": round(r.pct_diff, 4), "aligned": r.aligned}
                for k, r in recon.items()],
            "weekly_deviation": {"dates": self.dates, "values": [round(float(x), 4) for x in dev],
                                 "weeks_within_tol": within, "weeks_total": len(self.dates)},
            "unaligned": {
                "mismatch": [{**_ref(k), "pct_diff": round(float(p), 4)} for k, p in ua["mismatch"]],
                "raw_only": [_ref(k) for k in ua["raw_only"]],
                "processed_only": [_ref(k) for k in ua["processed_only"]],
            },
        }

    def summary(self) -> dict:
        return {
            "id": self.id, "env": self.env, "bmc": self.bmc, "refresh": self.refresh,
            "dates": self.dates,
            "domains": {d: self.counts(d) for d in self.proposals},
            "analysis": self.analysis(),
        }

    def mapping_payload(self, domain: str) -> dict:
        """Proposals for a domain, enriched with per-target processed series and
        active flags so the UI can draw sparklines (which targets carry values)."""
        import numpy as np
        out = []
        for p in self.proposals.get(domain, []):
            d = dump_proposal(p)
            for t in d["targets"]:
                s = self.engine.processed.get((t["var"], RegionKey.parse(t["region"])))
                if s is not None:
                    arr = np.asarray(s, float)
                    t["series"] = [round(float(x), 5) for x in arr]
                    t["active"] = bool(np.any(np.abs(arr) > 1e-9))
                else:
                    t["series"] = None
                    t["active"] = t["percent"] > 0
            out.append(d)
        return {"domain": domain, "proposals": out}

    def edit(self, domain: str, proposal_dicts: list[dict]) -> dict:
        props = [load_proposal(p) for p in proposal_dicts]
        self.proposals[domain] = props
        if domain == "raw_to_processed":
            delta = self.engine.apply_mapping(props)
            return {
                "changed_targets": [_ref(k) for k in delta.changed_targets],
                "analysis": self.analysis(),
            }
        return {"changed_targets": [], "analysis": self.analysis()}

    def extend(self, new_dates: list[str], new_raw: dict) -> dict:
        """Apply the +1-month extension and store the combined decomposition."""
        res = extend_engine(self.engine, new_dates, new_raw)
        self.combined = {"dates": res["dates"], "decomp": res["combined_decomp"]}
        totals = {_ref(k)["var"] + " " + _ref(k)["region"]: float(v.sum())
                  for k, v in res["new_decomp"].items()}
        return {
            "historical_weeks": len(self.dates),
            "new_weeks": len(new_dates),
            "combined_weeks": len(res["dates"]),
            "new_dates": list(new_dates),
            "overlap": res["overlap"],
            "new_contribution_total": round(sum(totals.values()), 4),
        }

    def insights_payload(self) -> dict:
        import numpy as np
        if self.combined:
            dates, decomp, scope = self.combined["dates"], self.combined["decomp"], "combined"
        else:
            dates, decomp, scope = self.dates, self.engine.decomp(), "historical"
        ins = compute_insights(dates, decomp, self.engine.raw)
        ins["scope"] = scope
        ins["total"] = round(ins["total"], 4)
        for r in ins["by_variable"]:
            r["contribution"] = round(r["contribution"], 4)
            r["pct"] = round(r["pct"], 2)
            if "roi" in r:
                r["roi"] = round(r["roi"], 4)
                r["invest"] = round(r["invest"], 2)
        for r in ins["by_region"]:
            r["contribution"] = round(r["contribution"], 4)
            r["pct"] = round(r["pct"], 2)
        ins["trend"]["values"] = [round(float(x), 4) for x in ins["trend"]["values"]]
        return ins

    def commit(self) -> dict:
        paths = {}
        for domain, props in self.proposals.items():
            paths[domain] = self._baseline.save(self.bmc, domain, props)
        return {"committed": True, "baseline_paths": paths}


class SessionService:
    def __init__(self, source_for_env: Callable[[str], object], baseline_store=None):
        self.source_for_env = source_for_env
        self.baseline = baseline_store or NoBaselineStore()
        self.sessions: dict[str, MappingSession] = {}

    def list_bmcs(self, env: str) -> list[str]:
        src = self.source_for_env(env)
        return src.list_bmcs(env) if hasattr(src, "list_bmcs") else []

    def list_refreshes(self, env: str, bmc: str) -> list[str]:
        return self.source_for_env(env).list_refreshes(bmc)

    def create(self, env: str, bmc: str, refresh: str) -> MappingSession:
        data: LoadedData = self.source_for_env(env).load(bmc, refresh)
        universe = RegionUniverse.from_regions([r for (_v, r) in data.processed])
        index = ProcessedIndex({(v, RegionKey.parse(r)): s for (v, r), s in data.processed.items()},
                               universe)
        proposals: dict[str, list[MappingProposal]] = {}
        domain_sources = {
            "raw_to_processed": data.raw,
            "processing_detail_to_processed": data.processing_details,
            "contribution_to_processed": data.contribution,
        }
        for domain in DOMAINS:
            src = domain_sources.get(domain) or {}
            if not src:
                continue
            resolver = Resolver(index, data.dates, self.baseline.baseline_dict(bmc, domain))
            sources = {(v, RegionKey.parse(r)): s for (v, r), s in src.items()}
            proposals[domain] = resolver.resolve_all(sources)

        engine = ReactiveEngine(data.dates, data.raw, data.processed, data.contribution_totals,
                                data.params, proposals.get("raw_to_processed", []))
        sess = MappingSession(id=str(uuid.uuid4())[:8], env=env, bmc=bmc, refresh=refresh,
                              dates=data.dates, proposals=proposals, engine=engine,
                              _baseline=self.baseline)
        self.sessions[sess.id] = sess
        return sess

    def get(self, sid: str) -> MappingSession:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

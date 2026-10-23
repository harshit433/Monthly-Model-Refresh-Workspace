"""Business insights from the decomposition.

Contribution per variable / region / over time, and ROI where a paired invest
(spend) variable exists. ROI = contribution / spend, pairing a media activity
variable with its `..._invest` sibling (same prefix up to `sub-brand-<X>`).
"""
from __future__ import annotations

import re

import numpy as np

from .regions import RegionKey

_INVEST = re.compile(r"(.*?sub-brand-[a-z0-9&\-]+)_", re.I)


def invest_name(var: str) -> str | None:
    m = _INVEST.match(var)
    return m.group(1) + "_invest" if m else None


def _lookup(raw: dict, var: str, region) -> np.ndarray | None:
    if var is None or raw is None:
        return None
    rk = region if isinstance(region, RegionKey) else RegionKey.parse(region)
    for key in ((var, rk), (var, rk.canonical)):
        if key in raw:
            return np.asarray(raw[key], float)
    return None


def insights(dates: list[str], decomp: dict, raw: dict | None = None) -> dict:
    per, total = [], 0.0
    trend = np.zeros(len(dates))
    region_tot: dict = {}

    for (var, region), ser in decomp.items():
        ser = np.asarray(ser, float)
        s = float(np.sum(ser))
        total += s
        trend = trend + ser
        rk = region if isinstance(region, RegionKey) else RegionKey.parse(region)
        region_tot[rk.canonical] = region_tot.get(rk.canonical, 0.0) + s
        row = {"var": var, "region": rk.canonical, "contribution": s}
        spend = _lookup(raw, invest_name(var), rk)
        if spend is not None and float(np.sum(spend)) > 0:
            row["invest"] = float(np.sum(spend))
            row["roi"] = s / row["invest"]
        per.append(row)

    for p in per:
        p["pct"] = (p["contribution"] / total * 100.0) if total else 0.0
    per.sort(key=lambda x: -x["contribution"])
    region = [{"region": r, "contribution": v, "pct": (v / total * 100.0 if total else 0.0)}
              for r, v in sorted(region_tot.items(), key=lambda x: -x[1])]
    return {
        "total": total,
        "by_variable": per,
        "by_region": region,
        "trend": {"dates": dates, "values": [float(x) for x in trend]},
    }

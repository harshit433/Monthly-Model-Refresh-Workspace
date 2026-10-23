"""New-month extension (Section 6).

Extend the model forward by one month of NEW data using the SAME verified
mapping and the SAME historical parameters/coefficients — never refitting.
Continuity across the boundary:

  * normalize the new month by the HISTORICAL max (not its own max);
  * Hill with the fitted params;
  * Adstock seeded from the last historical adstocked value (carry-over flows in);
  * Lag prefixed with the historical adstocked tail;
  * decomp with the historical coefficient.

The result is appended to the historical decomp to give the combined
(e.g. 25-month) decomposition.
"""
from __future__ import annotations

import numpy as np

from .engine import ReactiveEngine
from .regions import RegionKey
from .transforms import transform_stages

VarRef = tuple[str, RegionKey]


def extend(engine: ReactiveEngine, new_dates: list[str],
           new_raw: dict) -> dict:
    n = len(new_dates)
    nraw = {(v, RegionKey.parse(r)): np.asarray(s, float) for (v, r), s in new_raw.items()}
    coefs = engine.coefficients()
    hist_decomp = engine.decomp()
    hist_n = len(engine.dates)

    combined, new_decomp, new_lagged = {}, {}, {}
    for tkey, contribs in engine._contrib.items():
        # apply the mapping to the new month (same weights)
        nm = np.zeros(n)
        for skey, w in contribs:
            src = nraw.get(skey)
            if src is None:
                continue
            try:
                nm = nm + src * w.resolve(n, new_dates)
            except Exception:
                pass  # a fixed vector mask is historical-length; skip for new weeks
        params = engine.params.get(tkey)
        hist = transform_stages(engine._mapped[tkey], params)
        seed = float(hist["adstocked"][-1]) if hist["adstocked"].size else 0.0
        st = transform_stages(nm, params, adstock_seed=seed,
                              lag_hist_tail=hist["adstocked"], norm_max=hist["row_max"])
        nl = st["lagged"]
        nd = nl * coefs.get(tkey, 0.0)
        new_lagged[tkey] = nl
        new_decomp[tkey] = nd
        combined[tkey] = np.concatenate([hist_decomp.get(tkey, np.zeros(hist_n)), nd])

    return {
        "dates": list(engine.dates) + list(new_dates),
        "combined_decomp": combined,
        "new_decomp": new_decomp,
        "new_lagged": new_lagged,
        "overlap": sorted(set(engine.dates) & set(new_dates)),
    }

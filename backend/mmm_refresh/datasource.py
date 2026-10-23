"""Source data access.

`DataSource` loads the five source domains for a (BMC, refresh) into wide,
per-(var, region) weekly numpy series. `DatabricksSource` reads live Unity
Catalog tables (same tables as the notebook); `InMemorySource` serves a
supplied dataset for dev/tests without a cluster. `make_demo_data` builds a
small, self-consistent scenario (processed == what the mapping+transforms
reproduce) so the API runs end to end offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import EnvConfig
from .transforms import TransformParams, transform_series

VarRef = tuple[str, str]  # (var_name, region_canonical_str)


@dataclass
class LoadedData:
    dates: list[str]
    raw: dict[VarRef, np.ndarray] = field(default_factory=dict)
    processed: dict[VarRef, np.ndarray] = field(default_factory=dict)
    contribution: dict[VarRef, np.ndarray] = field(default_factory=dict)
    contribution_totals: dict[VarRef, float] = field(default_factory=dict)
    processing_details: dict[VarRef, np.ndarray] = field(default_factory=dict)
    params: dict[VarRef, TransformParams] = field(default_factory=dict)


def _pivot_long(rows, var_col, region_col, date_col, value_col):
    """rows: iterable of dict-like -> (sorted dates, {(var,region)->series})."""
    dates = sorted({str(r[date_col]) for r in rows})
    di = {d: i for i, d in enumerate(dates)}
    out: dict[VarRef, np.ndarray] = {}
    for r in rows:
        key = (str(r[var_col]), str(r[region_col]))
        arr = out.setdefault(key, np.zeros(len(dates)))
        v = r[value_col]
        arr[di[str(r[date_col])]] = float(v) if v is not None else 0.0
    return dates, out


def build_params(pd_rows) -> dict[VarRef, TransformParams]:
    """Combine processing-details rows (one per processor) into TransformParams.

    diminishing_hill -> K=value2, S=value3, max=value6 ; adstock -> value4 ;
    lag -> value5.
    """
    acc: dict[VarRef, dict] = {}
    for r in pd_rows:
        key = (str(r["var_name"]), str(r["region"]))
        proc = str(r.get("processor", "")).lower()
        d = acc.setdefault(key, {})
        if "hill" in proc or "diminish" in proc:
            d["K"], d["S"], d["max_val"] = _f(r.get("value2")), _f(r.get("value3")), _f(r.get("value6"))
        elif "adstock" in proc:
            d["adstock_rate"] = _f(r.get("value4"))
        elif "lag" in proc:
            v = _f(r.get("value5"))
            d["lag_value"] = int(v) if v is not None else None
    return {k: TransformParams(**v) for k, v in acc.items()}


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


class InMemorySource:
    """Serves preloaded LoadedData keyed by (bmc, refresh); for dev/tests."""

    def __init__(self, data: dict[tuple[str, str], LoadedData] | None = None):
        self._data = data or {}

    def put(self, bmc: str, refresh: str, data: LoadedData) -> None:
        self._data[(bmc, refresh)] = data

    def list_bmcs(self, env: str | None = None) -> list[str]:
        return sorted({b for (b, _r) in self._data})

    def list_refreshes(self, bmc: str) -> list[str]:
        return sorted({r for (b, r) in self._data if b == bmc})

    def load(self, bmc: str, refresh: str) -> LoadedData:
        if (bmc, refresh) not in self._data:
            raise KeyError(f"no data for {bmc} / {refresh}")
        return self._data[(bmc, refresh)]


class DatabricksSource:
    """Live Unity Catalog reader (same tables as the notebook).

    Needs `databricks-sql-connector` and a warehouse configured on the EnvConfig.
    region is already a STRING in raw/processed/contribution; in
    processing_details it is a STRUCT, rebuilt into the tuple-string in SQL.
    """

    def __init__(self, env: EnvConfig, access_token: str):
        self.env = env
        self.token = access_token

    def _connect(self):
        try:
            from databricks import sql  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("databricks-sql-connector is required for DatabricksSource") from e
        host, http = self.env.server_hostname, self.env.http_path
        if not (host and http):
            raise RuntimeError(f"env {self.env.name!r} has no SQL warehouse configured "
                               "(set DATABRICKS_HTTP_PATH and DATABRICKS_HOST/SERVER_HOSTNAME)")
        if self.token:
            return sql.connect(server_hostname=host, http_path=http, access_token=self.token)
        # No PAT: use the Databricks SDK credentials (e.g. a Databricks App's
        # service principal, or the local CLI profile). Needs databricks-sdk.
        try:  # pragma: no cover - needs cluster/app
            from databricks.sdk.core import Config
            cfg = Config(host=f"https://{host}")
            return sql.connect(server_hostname=host, http_path=http,
                               credentials_provider=lambda: cfg.authenticate)
        except Exception as e:  # pragma: no cover
            raise RuntimeError("no DATABRICKS_TOKEN set and SDK auth is unavailable; "
                               "set a token or install databricks-sdk") from e

    def list_bmcs(self, env: str | None = None) -> list[str]:  # pragma: no cover - needs cluster
        with self._connect() as conn:
            rows = self._query(conn, f"SELECT DISTINCT bmc FROM {self.env.table('avm')}")
        return sorted(str(r["bmc"]) for r in rows if r["bmc"] is not None)

    def _query(self, conn, sql_text: str) -> list[dict]:
        cur = conn.cursor()
        cur.execute(sql_text)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows

    def list_refreshes(self, bmc: str) -> list[str]:  # pragma: no cover - needs cluster
        with self._connect() as conn:
            rows = self._query(conn, f"""
                SELECT DISTINCT model_phase FROM {self.env.table('avm')}
                WHERE bmc = '{bmc}'""")
        return sorted(str(r["model_phase"]) for r in rows if r["model_phase"] is not None)

    def load(self, bmc: str, refresh: str) -> LoadedData:  # pragma: no cover - needs cluster
        f = lambda t: f"WHERE bmc = '{bmc}' AND model_phase = '{refresh}'"
        region_struct = (
            "CASE WHEN region.eki_store_format_mmm IS NULL "
            "THEN concat(\"('\", region.eki_sub_brand_mmm, \"',)\") "
            "ELSE concat(\"('\", region.eki_sub_brand_mmm, \"', '\", "
            "region.eki_store_format_mmm, \"')\") END AS region")
        with self._connect() as conn:
            raw_rows = self._query(conn, f"""
                SELECT var_name, region, date_format(date,'yyyy-MM-dd') date,
                       coalesce(cast(raw_value as double),0) raw_value
                FROM {self.env.table('raw_data')} {f('')}""")
            proc_rows = self._query(conn, f"""
                SELECT var_name, region, date_format(date,'yyyy-MM-dd') date, processed_value
                FROM {self.env.table('processed_data')} {f('')}""")
            contrib_rows = self._query(conn, f"""
                SELECT var_name, region, date_format(date,'yyyy-MM-dd') date, contribution_non_indexed
                FROM {self.env.table('contribution')} {f('')}""")
            pd_rows = self._query(conn, f"""
                SELECT var_name, {region_struct}, processor, value2, value3, value4, value5, value6
                FROM {self.env.table('processing_details')} {f('')}""")

        dates, raw = _pivot_long(raw_rows, "var_name", "region", "date", "raw_value")
        _, processed = _pivot_long(proc_rows, "var_name", "region", "date", "processed_value")
        _, contribution = _pivot_long(contrib_rows, "var_name", "region", "date", "contribution_non_indexed")
        totals = {k: float(np.sum(v)) for k, v in contribution.items()}
        return LoadedData(dates=dates, raw=raw, processed=processed, contribution=contribution,
                          contribution_totals=totals, params=build_params(pd_rows))


def make_demo_data() -> LoadedData:
    """A small Brazil_Centrum-like scenario covering direct / membership-split /
    rename / unmapped, built so the resolver auto-produces a varied grid and
    the mapping reconciles."""
    dates = ["2025-01-06", "2025-01-13", "2025-01-20", "2025-01-27",
             "2025-02-03", "2025-02-10", "2025-02-17", "2025-02-24"]
    media_p = TransformParams(K=0.5, S=2.0, max_val=1.0, adstock_rate=30.0, lag_value=1)
    SUBS = ["Access", "Multivitaminicos", "Others", "Select"]

    s1 = np.array([3., 4., 5., 4., 6., 5., 7., 6.])    # sales units (direct)
    s2 = np.array([1., 3., 6., 4., 2., 5., 7., 3.])    # media tv grps (direct)
    s3 = np.array([4., 4., 5., 5., 4., 4., 5., 5.])    # btl unattr invest (split)
    s5 = np.array([0., 0., 1., 0., 0., 1., 0., 0.])    # blkfriday flag (split, all regions)
    s6 = np.array([2., 4., 3., 5., 4., 6., 5., 4.])    # media digital-video (rename)

    raw = {
        ("sales__market__all-benefit__base__sales-units", "('Access',)"): s1,
        ("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps", "('Access',)"): s2,
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('All',)"): s3,
        ("dummy__access_blkfriday_promotion", "('All',)"): s5,
        ("media__digital-video__all-plac_all-plat_all-camp__sub-brand-access_regular_grps", "('Access',)"): s6,
        ("media__tv__all-plac_otv_all-camp__sub-brand-access_invest", "('Access',)"): np.array([8., 9., 7., 10., 8., 11., 9., 12.]),
        ("constant__macro_trend_index", "('Access',)"): np.array([1., 1., 2., 2., 3., 3., 4., 4.]),
    }
    params = {
        ("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps", "('Access',)"): media_p,
        ("media__digital-video__all-plac_all-plat_all-camp__sub-brand-access_special_grps", "('Access',)"): media_p,
    }
    processed = {}
    # direct
    processed[("sales__market__all-benefit__base__sales-units", "('Access',)")] = transform_series(s1, None)
    processed[("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps", "('Access',)")] = transform_series(s2, media_p)
    # btl split: 3 sub-brands carry the same value, Select is zero
    btl = "btl__shopper__all-btl__sub-brand-unattr_invest"
    for sb in ["Access", "Multivitaminicos", "Others"]:
        processed[(btl, f"('{sb}',)")] = transform_series(s3, None)
    processed[(btl, "('Select',)")] = np.zeros(len(dates))
    # blkfriday split: all four sub-brands active (equal)
    bf = "dummy__access_blkfriday_promotion"
    for sb in SUBS:
        processed[(bf, f"('{sb}',)")] = transform_series(s5, None)
    # rename target (digital-video regular -> special), same region
    processed[("media__digital-video__all-plac_all-plat_all-camp__sub-brand-access_special_grps", "('Access',)")] = transform_series(s6, media_p)
    # invest (spend) var — direct; used for ROI, not a transformed covariate
    inv = ("media__tv__all-plac_otv_all-camp__sub-brand-access_invest", "('Access',)")
    processed[inv] = transform_series(raw[inv], None)
    # constant__macro_trend_index has no processed counterpart -> unmapped

    totals = {k: 100.0 for k in processed}
    return LoadedData(dates=dates, raw=raw, processed=processed,
                      contribution_totals=totals, params=params)


def make_demo_new_month() -> tuple[list[str], dict]:
    """One new month (4 weeks) of raw data for the demo source variables,
    same shape/keys as the historical raw."""
    dates = ["2025-03-03", "2025-03-10", "2025-03-17", "2025-03-24"]
    raw = {
        ("sales__market__all-benefit__base__sales-units", "('Access',)"): np.array([6., 7., 6., 8.]),
        ("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps", "('Access',)"): np.array([4., 6., 3., 5.]),
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('All',)"): np.array([5., 5., 4., 6.]),
        ("dummy__access_blkfriday_promotion", "('All',)"): np.array([0., 1., 0., 0.]),
        ("media__digital-video__all-plac_all-plat_all-camp__sub-brand-access_regular_grps", "('Access',)"): np.array([5., 4., 6., 5.]),
        ("media__tv__all-plac_otv_all-camp__sub-brand-access_invest", "('Access',)"): np.array([10., 12., 9., 13.]),
    }
    return dates, raw

"""Environment configuration.

The environment (UAT / DEV / PROD) is chosen by the user in the app and
selects both the Unity Catalog location of the source tables and the ADLS base
path for the baseline Excel files. The exact catalog / mount strings per
environment are placeholders here — confirm them against the real notebook
paths when wiring the live cluster (the one remaining integration detail).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class EnvConfig:
    name: str
    catalog: str                       # schema/db holding the secondary_modelling_* tables
    adls_base: str                     # base path for per-BMC baseline/outputs
    server_hostname: str | None = None  # databricks SQL warehouse
    http_path: str | None = None

    def table(self, short: str) -> str:
        return f"{self.catalog}.secondary_modelling_{short}"

    def bmc_folder(self, bmc: str) -> str:
        return f"{self.adls_base.rstrip('/')}/{bmc}"

    def baseline_path(self, bmc: str, domain: str) -> str:
        return f"{self.bmc_folder(bmc)}/baselines/{domain}.xlsx"


# NOTE: catalog/adls strings are placeholders carrying the env token (e.g. 'uat').
ENVIRONMENTS: dict[str, EnvConfig] = {
    "dev": EnvConfig(
        name="dev", catalog="eki_refined_db",
        adls_base="dbfs:/mnt/mmmgen2devdatalake/Users_MMM/Harshit_Test",
    ),
    "uat": EnvConfig(
        name="uat", catalog="eki_refined_db_uat",
        adls_base="abfss://mmm@mmmgen2uatdatalake.dfs.core.windows.net/Users_MMM",
    ),
    "prod": EnvConfig(
        name="prod", catalog="eki_refined_db_prod",
        adls_base="abfss://mmm@mmmgen2proddatalake.dfs.core.windows.net/Users_MMM",
    ),
}

DOMAINS = ("raw_to_processed", "processing_detail_to_processed", "contribution_to_processed")


def _ov(env: str, key: str, default):
    """Env-var override: MMM_<KEY>_<ENV> wins, then MMM_<KEY>, then default.
    So the real catalog/ADLS/warehouse strings are set without code changes."""
    return os.environ.get(f"MMM_{key}_{env.upper()}") or os.environ.get(f"MMM_{key}") or default


def get_env(name: str) -> EnvConfig:
    key = (name or "").lower()
    if key not in ENVIRONMENTS:
        raise KeyError(f"unknown environment {name!r}; known: {list(ENVIRONMENTS)}")
    base = ENVIRONMENTS[key]
    return replace(
        base,
        catalog=_ov(key, "CATALOG", base.catalog),
        adls_base=_ov(key, "ADLS_BASE", base.adls_base),
        server_hostname=_ov(key, "DBX_HOST", base.server_hostname)
                        or os.environ.get("DATABRICKS_SERVER_HOSTNAME"),
        http_path=_ov(key, "DBX_HTTP", base.http_path)
                  or os.environ.get("DATABRICKS_HTTP_PATH"),
    )

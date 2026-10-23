"""Variable-name token parser + similarity.

Variable names follow a regular, token-delimited grammar (``__`` major,
``_``/``-`` minor), e.g.::

    media__tv__all-plac_ptv_all-camp__sub-brand-access_halo_grps__Multivitaminicos
    btl__shopper__all-btl__sub-brand-unattr_invest
    dummy_inf2025-05-01_media__digital-social__..._multivitaminicos_hero_impressions
    sales__market__all-benefit__base__sales-units__Access

`parse_variable` turns a name into a structured `VarToken`; `similarity`
scores two tokens for the resolver (names only — ratios are decided by the
numeric detection layer, never here).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES = ("media", "btl", "sales", "dummy", "constant")
METRICS = (
    "impressions", "clicks", "grps", "invest", "sales-units", "tdp",
    "base-price", "tpr", "distribution", "views", "reach", "spend",
)
EFFECTS = ("hero", "halo")
# low-signal structural tokens that shouldn't drive similarity
STOPWORDS = frozenset({
    "all", "plac", "plat", "camp", "all-plac", "all-plat", "all-camp",
    "all-btl", "all-benefit", "sub", "brand", "on", "base",
})

_TEMPORAL = re.compile(r"^dummy_(inf|sup)(\d{4}-\d{2}-\d{2})_(.+)$")
_SUBBRAND = re.compile(r"sub-brand-([a-z0-9&\-]+)", re.I)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class VarToken:
    raw: str
    category: str | None = None
    sub_brand: str | None = None          # content sub-brand (from sub-brand-X)
    metric: str | None = None
    effect: str | None = None             # hero / halo
    region_suffix: str | None = None      # trailing __Suffix (affected sub-brand)
    temporal_kind: str | None = None      # inf / sup
    temporal_date: str | None = None      # YYYY-MM-DD
    tokens: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_unattributed(self) -> bool:
        return self.sub_brand == "unattr"


def _minor_tokens(segment: str) -> list[str]:
    # split on '_' only: '-' joins a compound field (sales-units, all-plac,
    # sub-brand-access), so keep those intact as single tokens.
    return [t for t in segment.split("_") if t]


def parse_variable(name: str) -> VarToken:
    raw = (name or "").strip()
    text = raw
    temporal_kind = temporal_date = None

    m = _TEMPORAL.match(text)
    if m:
        temporal_kind, temporal_date, text = m.group(1), m.group(2), m.group(3)

    majors = [s for s in text.split("__") if s]
    category = None
    if majors and majors[0].lower() in CATEGORIES:
        category = majors[0].lower()

    # region suffix = trailing major segment that is a single Title-cased word
    region_suffix = None
    if len(majors) >= 2:
        last = majors[-1]
        if "_" not in last and "-" not in last and last[:1].isupper():
            region_suffix = last

    sub_brand = None
    sm = _SUBBRAND.search(text)
    if sm:
        sub_brand = sm.group(1).lower()

    # build token bag (minor tokens across all majors, dates/sub-brand marker stripped)
    bag: set[str] = set()
    for seg in majors:
        for tok in _minor_tokens(seg):
            tl = tok.lower()
            if _DATE.match(tl) or tl in {"sub-brand"}:
                continue
            bag.add(tl)
    if region_suffix:
        bag.discard(region_suffix.lower())

    metric = next((mt for mt in METRICS if mt in bag or mt.replace("-", "") in bag), None)
    effect = next((ef for ef in EFFECTS if ef in bag), None)

    return VarToken(
        raw=raw,
        category=category,
        sub_brand=sub_brand,
        metric=metric,
        effect=effect,
        region_suffix=region_suffix,
        temporal_kind=temporal_kind,
        temporal_date=temporal_date,
        tokens=frozenset(bag),
    )


def _weighted_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    def w(tok: str) -> float:
        return 0.3 if tok in STOPWORDS else 1.0
    inter = a & b
    union = a | b
    if not union:
        return 0.0
    num = sum(w(t) for t in inter)
    den = sum(w(t) for t in union)
    return num / den if den else 0.0


def similarity(a: VarToken, b: VarToken) -> float:
    """Name-similarity in [0, 1]. Used only to group/rank candidates."""
    score = 0.55 * _weighted_jaccard(a.tokens, b.tokens)
    if a.category and a.category == b.category:
        score += 0.18
    if a.metric and a.metric == b.metric:
        score += 0.15
    if a.sub_brand and a.sub_brand == b.sub_brand:
        score += 0.12
    return max(0.0, min(1.0, score))

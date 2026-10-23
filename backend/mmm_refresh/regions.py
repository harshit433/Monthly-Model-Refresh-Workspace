"""Region model.

Regions in the source data are stored as tuple-strings, e.g.::

    "('Core', 'Mass Market')"   # (sub_brand, store_format)
    "('Access',)"                # single-tuple sub_brand, no store format
    "('All',)"                   # the clubbed / aggregate region

`RegionKey` parses and canonicalises these, and `RegionUniverse` knows the
distinct sub-brands / store-formats for a BMC so it can decide whether a
raw -> processed region change is an *expansion* (All -> each sub-brand) or a
*clubbing* (each sub-brand -> All), which drives the split/aggregate choice.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

ALL = "All"


@dataclass(frozen=True)
class RegionKey:
    """A (sub_brand, store_format) region. store_format may be None."""

    sub_brand: str
    store_format: str | None = None

    @classmethod
    def parse(cls, value: object) -> "RegionKey":
        """Parse a tuple-string / tuple / RegionKey into a RegionKey."""
        if isinstance(value, RegionKey):
            return value
        if isinstance(value, (tuple, list)):
            parts = [str(p).strip() for p in value if p is not None and str(p).strip()]
        else:
            text = str(value).strip()
            parts = None
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, (tuple, list)):
                    parts = [str(p).strip() for p in parsed if p is not None and str(p).strip()]
                else:
                    parts = [str(parsed).strip()]
            except (ValueError, SyntaxError):
                # Fallback: pull quoted fragments out of "('A', 'B')"
                quoted = [a or b for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", text)]
                parts = [q.strip() for q in quoted if q.strip()] or [text.strip("() ,")]
        if not parts:
            raise ValueError(f"Could not parse region from {value!r}")
        sub = parts[0]
        fmt = parts[1] if len(parts) > 1 and parts[1] else None
        return cls(sub_brand=sub, store_format=fmt)

    @property
    def is_all(self) -> bool:
        return self.sub_brand == ALL

    @property
    def canonical(self) -> str:
        """Round-trip back to the tuple-string the source data uses."""
        if self.store_format:
            return f"('{self.sub_brand}', '{self.store_format}')"
        return f"('{self.sub_brand}',)"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.canonical


class RegionRelation:
    """Set relation between a source region and a set of target regions."""

    SAME = "same"
    EXPAND = "expand"      # source covers many targets (e.g. All -> sub-brands)
    CLUB = "club"          # many sources collapse into one target
    DISJOINT = "disjoint"  # unrelated


@dataclass
class RegionUniverse:
    """The distinct regions present for a BMC, used to expand ('All',)."""

    sub_brands: tuple[str, ...]
    store_formats: tuple[str | None, ...] = (None,)

    @classmethod
    def from_regions(cls, regions) -> "RegionUniverse":
        subs: list[str] = []
        fmts: list[str | None] = []
        for r in regions:
            rk = RegionKey.parse(r)
            if rk.sub_brand != ALL and rk.sub_brand not in subs:
                subs.append(rk.sub_brand)
            if rk.store_format not in fmts:
                fmts.append(rk.store_format)
        if not fmts:
            fmts = [None]
        return cls(sub_brands=tuple(subs), store_formats=tuple(fmts))

    def expand(self, region: RegionKey) -> list[RegionKey]:
        """Expand ('All',) to every concrete region; otherwise return [region]."""
        if not region.is_all:
            return [region]
        out: list[RegionKey] = []
        for sub in self.sub_brands:
            if region.store_format is not None:
                out.append(RegionKey(sub, region.store_format))
            else:
                for fmt in self.store_formats:
                    out.append(RegionKey(sub, fmt))
        return out

    def relation(self, source: RegionKey, targets: list[RegionKey]) -> str:
        tset = set(targets)
        if len(targets) == 1 and source in tset:
            return RegionRelation.SAME
        expanded = set(self.expand(source))
        if source.is_all and tset and tset <= expanded:
            return RegionRelation.EXPAND
        if len(targets) == 1 and targets[0].is_all:
            return RegionRelation.CLUB
        return RegionRelation.DISJOINT

import numpy as np
from mmm_refresh.regions import RegionKey, RegionRelation, RegionUniverse


def test_parse_single_and_pair():
    assert RegionKey.parse("('Access',)") == RegionKey("Access", None)
    assert RegionKey.parse("('Core', 'Mass Market')") == RegionKey("Core", "Mass Market")
    assert RegionKey.parse("('All',)").is_all


def test_canonical_roundtrip():
    for s in ["('Access',)", "('Core', 'Mass Market')", "('All',)"]:
        assert RegionKey.parse(s).canonical == s


def test_expand_all_to_subbrands():
    uni = RegionUniverse.from_regions(
        ["('Access',)", "('Multivitaminicos',)", "('Others',)", "('Select',)", "('All',)"]
    )
    expanded = uni.expand(RegionKey("All"))
    assert set(e.sub_brand for e in expanded) == {"Access", "Multivitaminicos", "Others", "Select"}


def test_region_relation_expand_and_same():
    uni = RegionUniverse.from_regions(["('Access',)", "('Multivitaminicos',)", "('All',)"])
    assert uni.relation(RegionKey("Access"), [RegionKey("Access")]) == RegionRelation.SAME
    rel = uni.relation(RegionKey("All"), [RegionKey("Access"), RegionKey("Multivitaminicos")])
    assert rel == RegionRelation.EXPAND

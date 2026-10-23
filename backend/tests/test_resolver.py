import numpy as np
from mmm_refresh.regions import RegionKey, RegionUniverse
from mmm_refresh.resolver import ProcessedIndex, Resolver


def _rk(s):
    return RegionKey.parse(s)


def build_processed():
    """A small processed universe mirroring real Brazil_Centrum patterns."""
    series = {
        # direct match
        ("sales__market__all-benefit__base__sales-units", "('Access',)"): np.array([10., 12., 11.]),
        # region split (same name, 4 sub-brands): 3 carry equal values, Select is zero
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('Access',)"): np.array([4., 4., 4.]),
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('Multivitaminicos',)"): np.array([4., 4., 4.]),
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('Others',)"): np.array([4., 4., 4.]),
        ("btl__shopper__all-btl__sub-brand-unattr_invest", "('Select',)"): np.array([0., 0., 0.]),
        # rename target (name differs from source, same region)
        ("media__digital-social__all-camp__CR-campaign_hero_impressions", "('Multivitaminicos',)"): np.array([7., 8., 9.]),
        # aggregate target (N sources sum here)
        ("sales__market__all-benefit__base__sales-units", "('Others',)"): np.array([9., 9., 9.]),
    }
    uni = RegionUniverse.from_regions([
        "('Access',)", "('Multivitaminicos',)", "('Others',)", "('Select',)", "('All',)",
    ])
    return ProcessedIndex(series, uni), uni


def test_direct_exact_match():
    idx, uni = build_processed()
    r = Resolver(idx)
    p = r.resolve_variable("sales__market__all-benefit__base__sales-units", "('Access',)",
                           np.array([10., 12., 11.]))
    assert p.action == "direct" and p.confidence > 0.95 and p.status == "suggested"


def test_region_split_membership_three_active_one_zero():
    idx, uni = build_processed()
    r = Resolver(idx)
    src = np.array([10., 10., 10.])
    p = r.resolve_variable("btl__shopper__all-btl__sub-brand-unattr_invest", "('All',)", src)
    assert p.action == "split"
    assert p.detection.kind == "membership" and p.detection.reconciles
    # 3 regions active (weight 1), Select inactive (weight 0)
    active = {t.region.sub_brand: t for t in p.targets if t.percent == 100.0}
    assert set(active) == {"Access", "Multivitaminicos", "Others"}
    select = next(t for t in p.targets if t.region.sub_brand == "Select")
    assert select.percent == 0.0 and select.weight.value == 0.0
    assert p.confidence >= 0.9


def test_rename_detected_by_similarity_and_series():
    idx, uni = build_processed()
    r = Resolver(idx)
    # inf dummy of a social-impressions var, same region, identical series -> rename to CR-campaign
    p = r.resolve_variable(
        "dummy_inf2025-05-01_media__digital-social__all-camp__sub-brand-multivitaminicos_hero_impressions",
        "('Multivitaminicos',)", np.array([7., 8., 9.]))
    assert p.action == "rename"
    assert p.targets[0].var == "media__digital-social__all-camp__CR-campaign_hero_impressions"


def test_aggregate_region_clubbing():
    # same variable split across sub-brands in raw, clubbed to ('All',) in processed
    series = {
        ("media__competitor-tv__all-camp__sub-brand-unattr_grps", "('All',)"): np.array([9., 9., 9.]),
    }
    uni = RegionUniverse.from_regions(["('Access',)", "('Multivitaminicos',)", "('All',)"])
    idx = ProcessedIndex(series, uni)
    r = Resolver(idx)
    sources = {
        ("media__competitor-tv__all-camp__sub-brand-unattr_grps", _rk("('Access',)")): np.array([5., 5., 5.]),
        ("media__competitor-tv__all-camp__sub-brand-unattr_grps", _rk("('Multivitaminicos',)")): np.array([4., 4., 4.]),
    }
    props = r.resolve_all(sources)
    agg = [p for p in props if p.action == "aggregate"]
    assert len(agg) == 1
    assert len(agg[0].sources) == 2
    assert agg[0].targets[0].region == _rk("('All',)")
    assert agg[0].confidence > 0.9


def test_dissimilar_names_stay_unmapped_not_hallucinated():
    # distribution/tdp and trade/tpr do NOT token-match sales-units: the resolver
    # must not invent an aggregate; these come from baseline or manual grouping.
    idx, uni = build_processed()
    r = Resolver(idx)
    sources = {
        ("sales__brand__all-benefit__distribution_tdp__Others", _rk("('Others',)")): np.array([5., 5., 5.]),
        ("sales__brand__all-benefit__trade_tpr__Others", _rk("('Others',)")): np.array([4., 4., 4.]),
    }
    props = r.resolve_all(sources)
    assert all(p.action == "unmapped" for p in props)


def test_unmapped_when_no_candidate():
    idx, uni = build_processed()
    r = Resolver(idx)
    p = r.resolve_variable("constant__some_unknown_thing_xyz", "('Access',)", np.array([1., 1., 1.]))
    assert p.action == "unmapped" and p.status == "unmapped"


def test_baseline_is_preferred_and_reverified():
    idx, uni = build_processed()
    from mmm_refresh.resolver import MappingProposal, TargetRef
    from mmm_refresh.actions import Weight
    base = {
        ("sales__market__all-benefit__base__sales-units", _rk("('Access',)")): MappingProposal(
            sources=[("sales__market__all-benefit__base__sales-units", _rk("('Access',)"))],
            action="direct",
            targets=[TargetRef("sales__market__all-benefit__base__sales-units", _rk("('Access',)"),
                               Weight.scalar(1.0), 100.0)],
        )
    }
    r = Resolver(idx, baseline=base)
    p = r.resolve_variable("sales__market__all-benefit__base__sales-units", "('Access',)",
                           np.array([10., 12., 11.]))
    assert p.provenance == "baseline" and p.confidence >= 0.9

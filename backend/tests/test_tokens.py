from mmm_refresh.tokens import parse_variable, similarity


def test_parse_media_halo_with_suffix():
    t = parse_variable(
        "media__tv__all-plac_ptv_all-camp__sub-brand-access_halo_grps__Multivitaminicos"
    )
    assert t.category == "media"
    assert t.sub_brand == "access"
    assert t.metric == "grps"
    assert t.effect == "halo"
    assert t.region_suffix == "Multivitaminicos"


def test_parse_unattributed_invest():
    t = parse_variable("btl__shopper__all-btl__sub-brand-unattr_invest")
    assert t.category == "btl"
    assert t.is_unattributed
    assert t.metric == "invest"
    assert t.region_suffix is None


def test_parse_temporal_prefix():
    t = parse_variable(
        "dummy_inf2025-05-01_media__digital-social__all-camp__sub-brand-multivitaminicos_hero_impressions"
    )
    assert t.temporal_kind == "inf"
    assert t.temporal_date == "2025-05-01"
    assert t.metric == "impressions"
    assert t.sub_brand == "multivitaminicos"


def test_similarity_orders_related_above_unrelated():
    a = parse_variable("media__tv__all-plac_otv_all-camp__sub-brand-access_hero_grps")
    near = parse_variable("media__tv__all-plac_ptv_all-camp__sub-brand-access_hero_grps")
    far = parse_variable("sales__brand__all-benefit__price__base-price")
    assert similarity(a, near) > similarity(a, far)
    assert similarity(a, a) > 0.9

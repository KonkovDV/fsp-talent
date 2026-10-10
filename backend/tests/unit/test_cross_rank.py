from app.services.search.cross_rank import blend_pair, cross_enabled


def test_the_pair_model_is_off_and_the_map_stays_put():
    assert cross_enabled() is False
    fused = {"a": 0.5, "b": 0.2}
    assert blend_pair(fused, None) == fused
    assert blend_pair(fused, []) == fused


def test_a_pair_order_only_nudges_the_query_signal():
    fused = {"a": 1.0, "b": 1.0}
    moved = blend_pair(fused, ["b", "a"])
    assert moved["b"] > moved["a"]
    assert moved["b"] < 1.0

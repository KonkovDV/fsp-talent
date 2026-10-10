from app.services.search.cross_rank import RERANK_HEAD, cross_enabled, rerank_text


def test_the_pair_model_is_off_and_the_map_stays_put():
    assert cross_enabled() is False
    assert RERANK_HEAD == 50
    fused = {"a": 0.5, "b": 0.2}
    assert rerank_text(fused, None) == fused
    assert rerank_text(fused, []) == fused


def test_the_pair_model_reorders_the_head_and_leaves_the_tail_behind():
    fused = {"c": 0.9, "a": 0.5, "b": 0.2}
    moved = rerank_text(fused, ["b", "a"])
    order = sorted(moved, key=lambda pid: (-moved[pid], str(pid)))
    assert order == ["b", "a", "c"]
    assert moved["b"] > moved["a"] > moved["c"]

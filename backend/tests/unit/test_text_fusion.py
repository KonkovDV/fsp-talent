"""The query factor is words and meaning. A stronger FSP result cannot move it."""
from app.services.search.pipeline import fuse_text


def test_text_fusion_ignores_a_discipline_score_and_a_test():
    lex = ["security-person", "robotics-person", "other"]
    dense = ["other", "security-person"]
    first = fuse_text(lex, dense)
    # LCB and theta are not inputs. The same word order produces the same map.
    assert fuse_text(list(lex), list(dense)) == first
    assert fuse_text(lex, None) != fuse_text(list(reversed(lex)), None)
    assert "security-person" in first and "robotics-person" in first


def test_an_empty_query_fuses_to_nothing():
    assert fuse_text([], None) == {}


def test_equal_word_scores_share_one_query_rank():
    order = ["security-person", "robotics-person"]
    scores = {"security-person": 0.5, "robotics-person": 0.5}
    fused = fuse_text(order, None, scores)
    assert fused["security-person"] == fused["robotics-person"]

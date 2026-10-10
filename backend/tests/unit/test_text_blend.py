import pytest

from app.services.search.pipeline import MEANING_SHARE, RRF_K, RULES_SHARE, fuse_text


def test_without_a_meaning_vector_the_word_rank_stays():
    words = fuse_text(["a", "b"])
    assert fuse_text(["a", "b"], None) == words
    assert fuse_text(["a", "b"], []) == words


def test_meaning_takes_fifteen_percent_and_words_keep_eighty_five():
    words = fuse_text(["a"])
    mixed = fuse_text(["a"], ["b"])
    assert mixed["a"] == words["a"] * RULES_SHARE
    assert mixed["b"] == pytest.approx(MEANING_SHARE / (RRF_K + 1))
    assert RULES_SHARE == 0.85 and MEANING_SHARE == 0.15

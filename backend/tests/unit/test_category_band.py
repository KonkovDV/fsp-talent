"""Category-first order is a measurement. The product sort does not pass bands."""
from app.services.matching import category_band
from app.services.search.pipeline import order_pool


def test_exact_category_beats_a_higher_score_from_another_class():
    assert category_band("backend", "middle", "backend", "middle") == 0
    assert category_band("backend", "junior", "backend", "middle") == 1
    assert category_band("fullstack", "middle", "backend", "middle") == 1
    assert category_band("security", "middle", "backend", "middle") == 2
    assert category_band("backend", "lead", "backend", "middle") == 2
    scores = {"exact": 0.40, "other": 0.90}
    ordered = order_pool(["other", "exact"], scores, {}, {})
    assert ordered[0] == "other"
    banded = order_pool(["other", "exact"], scores, {}, {}, bands={"exact": 0, "other": 2})
    assert banded == ["exact", "other"]


def test_inside_one_band_the_score_order_stays():
    scores = {"a": 0.2, "b": 0.8, "c": 0.5}
    bands = {"a": 0, "b": 0, "c": 0}
    assert order_pool(["a", "b", "c"], scores, {}, {}, bands=bands) == ["b", "c", "a"]

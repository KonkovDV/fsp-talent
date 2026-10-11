from app.services import cat
from app.validation import wle_eap


def _items(correct):
    return [cat.Response(1.5, b / 2, 0.02, ok) for b, ok in zip(range(-4, 4), correct, strict=True)]


def test_wle_is_finite_and_ordered():
    low = wle_eap.wle(_items([False] * 8))
    mid = wle_eap.wle(_items([True] * 4 + [False] * 4))
    high = wle_eap.wle(_items([True] * 8))
    assert -4.0 <= low < mid < high <= 4.0


def test_grade_index_uses_product_cuts():
    assert wle_eap.grade_index(-3.0) == 0
    assert wle_eap.grade_index(-0.5) == 3
    assert wle_eap.grade_index(2.0) == 5


def test_small_report():
    res = wle_eap.summary(wle_eap.simulate(40, 3))
    for name in ("EAP", "WLE"):
        assert 0 < res[name]["rmse"] < 1.5
        assert 0 <= res[name]["exact"] <= 1
    assert "WLE" in wle_eap.markdown({3: res}, 40)

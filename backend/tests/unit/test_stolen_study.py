from app.validation.assessment import _wilson, stolen_study


def test_wilson_interval_contains_share():
    lo, hi = _wilson(137, 2400)
    assert lo < 137 / 2400 < hi
    assert round(lo, 3) == 0.048 and round(hi, 3) == 0.067


def test_stolen_study_prints_pooled_row():
    text = stolen_study([7], n_calib=200, stolen_n=4)
    assert "| 7 |" in text and "95 % ДИ Уилсона" in text

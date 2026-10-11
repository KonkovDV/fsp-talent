"""NEW-2 product side: a grade within one SE of its cut is marked on the card, not hidden."""
import inspect

from app.services.cat import CUTS, is_borderline
from app.services.search import pipeline


def test_borderline_is_one_standard_error_from_the_cut():
    cut = CUTS["middle"]
    assert is_borderline(cut + 0.2, 0.3, "middle")
    assert not is_borderline(cut + 0.4, 0.3, "middle")
    assert not is_borderline(None, 0.3, "middle") and not is_borderline(cut, None, "middle")
    assert not is_borderline(cut, 0.3, "guru")


def test_card_carries_the_flag_only_for_the_assessed_header_grade():
    source = inspect.getsource(pipeline._build_cards)
    assert '"grade_borderline": pid in borderline' in source
    assert 'cat_c.grade_source == "assessed"' in source and "c.grade == cat_c.grade" in source

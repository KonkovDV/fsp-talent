"""A leakable wording that beats the model, while fresh numbers do not, asks for a look."""
from types import SimpleNamespace

from app.api.v1.assessment import _review_notes
from app.services.form_gap import FORM_GAP, form_gap
from app.services.session_marks import integrity_level


def _row(kind, correct, a=1.2, b=0.0, c=0.2):
    return SimpleNamespace(kind=kind, is_correct=correct, a=a, b=b, c=c)


def test_too_few_items_of_either_form_is_silent():
    rows = [_row("concept", True)] * 3 + [_row("code", False)] * 2
    assert form_gap(rows, 0.0) is None


def test_concept_ahead_of_code_is_a_review_and_not_a_risk_point():
    rows = [_row("concept", True)] * 3 + [_row("code", False)] * 3
    gap = form_gap(rows, 0.0)
    assert gap["review"] is True and gap["gap"] >= FORM_GAP
    flags = {"form_gap": gap}
    assert "form_gap" not in integrity_level(flags)["signals"]
    notes = _review_notes(flags)
    assert len(notes) == 1 and "Грейд не изменён" in notes[0]


def test_the_same_residual_on_both_forms_is_not_a_review():
    rows = [_row("concept", True), _row("concept", False), _row("concept", True),
            _row("code", True), _row("code", False), _row("code", True)]
    gap = form_gap(rows, 0.0)
    assert gap["review"] is False and abs(gap["gap"]) < 1e-9


def test_the_anchor_comes_from_the_code_items_not_the_leaked_wordings():
    rows = [_row("concept", True)] * 6 + [_row("code", False)] * 4
    gap = form_gap(rows, 2.5)
    assert gap["anchor_theta"] < 0.0
    assert gap["review"] is True

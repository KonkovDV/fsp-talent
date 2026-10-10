import pytest

from app.services.interview_code import CodeStale, apply_code_draft, code_view


def test_draft_keeps_the_last_snapshots_and_rejects_a_stale_tab():
    version, text, shots = apply_code_draft(0, 0, "  print(1) ", [])
    assert version == 1 and text == "print(1)" and shots == [{"version": 1, "text": "print(1)"}]
    version, text, shots = apply_code_draft(version, version, "print(2)", shots * 8)
    assert version == 2 and len(shots) == 8 and shots[-1]["text"] == "print(2)"
    with pytest.raises(CodeStale):
        apply_code_draft(2, 1, "print(3)", shots)


def test_the_view_has_no_grade_and_no_model_score():
    view = code_view({"id": "sum"}, "сложите", "print(1)", 1, [{"version": 1, "text": "print(1)"}], "условие другое")
    assert "grade" not in view and "score" not in view
    assert view["dispute"] == "условие другое"

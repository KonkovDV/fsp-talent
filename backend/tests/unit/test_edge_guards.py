"""Branches the published coverage run left dark: guards, not new product rules."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.rls import bypass_rls, current, reset_rls
from app.legal import _parse
from app.services.fsp.relevance import lcb_for_need
from app.services.inn import _digit, inn_is_valid
from app.services.interviews import moscow_start, slot_view
from app.services.psychometrics import bank_curve
from app.services.skills import read_resume_evidence, with_resume_token
from app.services.tasks import employer_view, validate_reference


def test_inn_rejects_letters_and_checks_twelve_digits():
    assert not inn_is_valid("7707083893a")
    body = "5001007322"
    n11 = _digit(body, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
    eleven = body + n11
    n12 = _digit(eleven, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
    inn = eleven + n12
    assert inn_is_valid(inn)
    assert not inn_is_valid(inn[:-1] + ("0" if inn[-1] != "0" else "1"))


def test_rls_bypass_is_visible_to_the_request():
    token = bypass_rls()
    try:
        assert current()["bypass"] is True
    finally:
        reset_rls(token)


def test_an_unknown_specialization_has_no_curve():
    with pytest.raises(ValueError):
        bank_curve("not-a-spec")


def test_moscow_time_rejects_a_zone_and_a_slot_reads_the_wall_clock():
    with pytest.raises(ValueError):
        moscow_start("2026-10-15", "14:00+03:00")
    row = SimpleNamespace(
        id=uuid.uuid4(), starts_at=datetime(2026, 10, 15, 11, tzinfo=UTC),
        format="online", place=None, chosen=False, outcome=None,
    )
    view = slot_view(row)
    assert view["date"] == "2026-10-15"
    assert view["time"] == "14:00"


def test_an_unknown_answer_type_is_rejected_and_the_owner_sees_the_reference():
    with pytest.raises(ValueError):
        validate_reference("essay", [], None, None)
    task = SimpleNamespace(
        id=uuid.uuid4(), title="Задача", statement="Условие", answer_type="open",
        options=[], correct_index=None, reference_number=None, visibility="public",
        specialization="backend", candidate_id=None, vacancy_id=None, deadline=None,
        is_open=True, created_at=None,
    )
    view = employer_view(task)
    assert view["title"] == "Задача"
    assert view["submissions"] == 0


def test_a_broken_resume_token_proves_nothing_and_an_empty_parse_has_no_token():
    assert read_resume_evidence("not-a-token", "person") == set()
    parsed = with_resume_token("person", {"skills": [{"name": "", "source_quote": ""}]})
    assert parsed["resume_token"] is None


def test_a_role_with_profile_disciplines_and_no_scores_in_either_bucket_is_neutral():
    # The empty map returns earlier. A filter for a discipline that is absent still names nothing.
    assert lcb_for_need("security", {}, discipline="security") == (0.0, None, None)


def test_legal_text_without_front_matter_is_refused(tmp_path):
    bare = tmp_path / "bare.md"
    bare.write_text("просто текст", encoding="utf-8")
    with pytest.raises(ValueError):
        _parse(bare)

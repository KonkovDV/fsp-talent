from datetime import date

from app.models.participant import Participant
from app.services.vacancies import match_vacancy, status_after_close


def _candidate(**extra):
    base = {
        "role": "backend", "grade": "middle", "skills": ["Python", "FastAPI", "PostgreSQL"],
        "disciplines": [{"discipline": "algorithmic", "best_rank": "I"}], "is_minor": False,
    }
    base.update(extra)
    return base


def _vacancy(**extra):
    base = {
        "role": "backend", "grade": "middle", "discipline": "algorithmic", "min_rank": "II",
        "skills": ["Python", "Go"], "allows_minors": False, "is_open": True,
    }
    base.update(extra)
    return base


def test_match_counts_skills_and_rejects_a_minor_without_permission():
    hit = match_vacancy(_candidate(), _vacancy())
    assert hit is not None and hit["matched_skills"] == ["Python"] and "Go" in hit["missing_skills"]
    assert match_vacancy(_candidate(is_minor=True), _vacancy()) is None
    assert match_vacancy(_candidate(is_minor=True), _vacancy(allows_minors=True)) is not None


def test_closing_a_vacancy_ends_an_open_application_and_keeps_a_refusal():
    assert status_after_close("applied") == "closed"
    assert status_after_close("reviewing") == "closed"
    assert status_after_close("invited") == "closed"
    assert status_after_close("rejected") is None
    assert status_after_close("closed") is None


def test_match_respects_role_grade_and_rank():
    assert match_vacancy(_candidate(role="frontend"), _vacancy()) is None
    assert match_vacancy(_candidate(grade="junior"), _vacancy(grade="senior")) is None
    assert match_vacancy(_candidate(grade="lead"), _vacancy(grade="senior")) is not None
    assert match_vacancy(_candidate(grade="lead"), _vacancy(grade="junior")) is None
    assert match_vacancy(_candidate(grade="middle"), _vacancy(grade="senior")) is not None
    assert match_vacancy(_candidate(grade="intern"), _vacancy(grade="senior", grade_match="exact")) is None
    assert match_vacancy(_candidate(grade="intern"), _vacancy(grade="senior", grade_match="any")) is not None
    assert match_vacancy(_candidate(disciplines=[{"discipline": "algorithmic", "best_rank": "III"}]),
                         _vacancy(min_rank="I")) is None


def test_birthday_overrides_a_stale_minor_flag():
    adult = Participant(is_visible=True, is_minor=True, minor_consent_given=False, birth_date=date(2000, 1, 1))
    assert adult.minor_now(date(2026, 10, 4)) is False
    assert adult.discoverable
    child = Participant(is_visible=True, is_minor=False, minor_consent_given=False, birth_date=date(2012, 5, 1))
    assert child.minor_now(date(2026, 10, 4)) is True
    assert not child.discoverable


def test_a_candidate_without_a_test_still_sees_published_vacancies():
    # ТЗ 2.1: the general list of published vacancies is open before any test.
    fresh = _candidate(role=None, grade=None, disciplines=[])
    hit = match_vacancy(fresh, _vacancy(discipline=None, min_rank=None, grade="senior", grade_match="exact"))
    assert hit is not None
    assert any("не подтверждён" in w for w in hit["why"])
    # Hard filters other than the grade still hold.
    assert match_vacancy(fresh, _vacancy()) is None   # needs an FSP discipline
    assert match_vacancy({**fresh, "is_minor": True}, _vacancy(discipline=None)) is None
    assert match_vacancy(fresh, _vacancy(discipline=None, is_open=False)) is None


def test_an_ungraded_card_is_marked_and_a_foreign_role_is_still_cut():
    fresh = _candidate(role="backend", grade=None, disciplines=[])
    open_any = _vacancy(discipline=None, min_rank=None)
    assert match_vacancy(fresh, open_any)["match"] == "not_assessed"
    assert "мидл" in " ".join(match_vacancy(fresh, open_any)["why"])
    assert match_vacancy(fresh, {**open_any, "role": "frontend"}) is None
    assert match_vacancy(_candidate(), _vacancy())["match"] == "matched"

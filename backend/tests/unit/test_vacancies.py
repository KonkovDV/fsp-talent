from datetime import date

from app.models.participant import Participant
from app.services.vacancies import match_vacancy


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


def test_match_respects_role_grade_and_rank():
    assert match_vacancy(_candidate(role="frontend"), _vacancy()) is None
    assert match_vacancy(_candidate(grade="junior"), _vacancy(grade="senior")) is None
    assert match_vacancy(_candidate(grade="lead"), _vacancy(grade="senior")) is not None
    assert match_vacancy(_candidate(disciplines=[{"discipline": "algorithmic", "best_rank": "III"}]),
                         _vacancy(min_rank="I")) is None


def test_birthday_overrides_a_stale_minor_flag():
    adult = Participant(is_visible=True, is_minor=True, minor_consent_given=False, birth_date=date(2000, 1, 1))
    assert adult.minor_now(date(2026, 10, 4)) is False
    assert adult.discoverable
    child = Participant(is_visible=True, is_minor=False, minor_consent_given=False, birth_date=date(2012, 5, 1))
    assert child.minor_now(date(2026, 10, 4)) is True
    assert not child.discoverable

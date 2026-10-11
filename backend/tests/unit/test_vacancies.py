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
    # SDK-01: a rank below the vacancy minimum is not a filter, only a missing boost.
    low_rank = match_vacancy(_candidate(disciplines=[{"discipline": "algorithmic", "best_rank": "III"}]),
                             _vacancy(min_rank="I"))
    assert low_rank is not None and low_rank["fsp_match"] is False


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
    assert match_vacancy(fresh, _vacancy(role=None, grade=None)) is not None   # FSP discipline is not a gate
    assert match_vacancy({**fresh, "is_minor": True}, _vacancy(discipline=None)) is None
    assert match_vacancy(fresh, _vacancy(discipline=None, is_open=False)) is None


def test_an_ungraded_card_is_marked_and_a_foreign_role_is_still_cut():
    fresh = _candidate(role="backend", grade=None, disciplines=[])
    open_any = _vacancy(discipline=None, min_rank=None)
    assert match_vacancy(fresh, open_any)["match"] == "not_assessed"
    assert "мидл" in " ".join(match_vacancy(fresh, open_any)["why"])
    assert match_vacancy(fresh, {**open_any, "role": "frontend"}) is None
    assert match_vacancy(_candidate(), _vacancy())["match"] == "matched"


def test_an_ungraded_candidate_sees_a_graded_vacancy_but_must_take_the_test_to_apply():
    fresh = _candidate(grade=None, disciplines=[])
    graded = match_vacancy(fresh, _vacancy(discipline=None, min_rank=None, grade="senior"))
    assert graded["needs_test"] is True
    any_grade = match_vacancy(fresh, _vacancy(discipline=None, min_rank=None, grade="senior", grade_match="any"))
    assert any_grade["needs_test"] is False
    assert match_vacancy(_candidate(), _vacancy())["needs_test"] is False


def test_fsp_history_boosts_but_never_gates_a_vacancy():
    # ТЗ 2: FSP achievements raise a candidate, a candidate without FSP history keeps the whole list (SDK-01).
    no_fsp = _candidate(disciplines=[])
    hit = match_vacancy(no_fsp, _vacancy())
    assert hit is not None and hit["fsp_match"] is False
    assert hit["needs_test"] is False
    assert any("не обязательны" in w for w in hit["why"])
    with_fsp = match_vacancy(_candidate(), _vacancy())
    assert with_fsp["fsp_match"] is True
    assert any(w.startswith("Есть результаты ФСП") for w in with_fsp["why"])
    other = match_vacancy(_candidate(disciplines=[{"discipline": "security", "best_rank": "I"}]), _vacancy())
    assert other is not None and other["fsp_match"] is False
    assert match_vacancy(no_fsp, _vacancy(discipline=None, min_rank=None))["fsp_match"] is False

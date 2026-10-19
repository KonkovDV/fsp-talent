from datetime import UTC, datetime, timedelta

from app.services.matching import CandidateFacts, NeedSpec, freshness_of, score

NEED = NeedSpec(role="backend", grade="middle", skills=("Python",))


def _facts(when: datetime | None) -> CandidateFacts:
    return CandidateFacts(
        role="backend", grade="middle", grade_source="assessed",
        skills={"Python": "test_confirmed"}, test_p=0.8, test_spec="backend", tested_at=when,
    )


def test_no_date_leaves_the_level_alone():
    now = datetime.now(UTC)
    assert freshness_of(None, now) == (0.0, None)
    assert freshness_of(now - timedelta(days=200), now)[0] == 0.15
    assert score(NEED, _facts(None)).score == score(NEED, _facts(now - timedelta(days=10))).score


def test_an_old_confirmation_keeps_the_score_and_says_the_error_is_wider():
    now = datetime.now(UTC)
    fresh = score(NEED, _facts(now - timedelta(days=10)))
    old = score(NEED, _facts(now - timedelta(days=400)))
    assert old.score == fresh.score
    assert any(reason.code == "TEST_FRESH" and "погрешность шире" in reason.text for reason in old.reasons)

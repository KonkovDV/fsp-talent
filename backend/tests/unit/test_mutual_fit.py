from app.services.matching import CandidateFacts, NeedSpec, mutual_fit, score

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))


def _person(**kw) -> CandidateFacts:
    base = dict(role="backend", grade="middle", grade_source="declared",
                skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"},
                test_p=0.9)
    base.update(kw)
    return CandidateFacts(**base)


def test_a_zero_opportunity_is_not_rescued_by_skills():
    assert mutual_fit(1.0, 0.0, 1.0) == 0.0


def test_the_fsp_bound_moves_the_list_score_and_not_the_mutual_number():
    low = score(NEED, _person(fsp_lcb=0.1))
    high = score(NEED, _person(fsp_lcb=0.9))
    assert high.score > low.score
    assert high.mutual == low.mutual


def test_a_hard_format_miss_stays_in_the_score_and_zeroes_the_mutual_number():
    need = NeedSpec(role="backend", grade="middle", skills=("Python",), work_format="remote")
    result = score(need, _person(work_formats=("office",)))
    assert result.score > 0
    assert result.mutual == 0.0
    assert result.rejected_by == ["format"]

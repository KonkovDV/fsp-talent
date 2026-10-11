"""Audit 2026-10 H-2 / audit-2 N-7 (P0-2): linking an FSP history never lowers the employer score.

Property test over the whole matching input space (hypothesis). Before the fix FSP_LIFT="mean"
averaged the test with the FSP factor, so a candidate with test 0.80 and one plain participation fell
to 0.43 evidence and below the same candidate without FSP. A rational candidate would not link FSP ID.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services import matching
from app.services.matching import CandidateFacts, NeedSpec, score

ROLES = ("backend", "frontend", "ml", "qa", "security")
GRADES = ("junior", "middle", "senior")
TRUST = ("self_reported", "resume_confirmed", "test_confirmed")


@st.composite
def cases(draw):
    role = draw(st.sampled_from(ROLES))
    need = NeedSpec(role=draw(st.sampled_from(ROLES)), grade=draw(st.sampled_from(GRADES)),
                    skills=tuple(draw(st.lists(st.sampled_from(("Python", "Go", "SQL", "React")),
                                               min_size=1, max_size=3, unique=True))))
    test_p = draw(st.one_of(st.none(), st.floats(0.0, 1.0)))
    base = dict(role=role, grade=draw(st.sampled_from(GRADES)),
                grade_source=draw(st.sampled_from(("declared", "assessed"))),
                skills={s: draw(st.sampled_from(TRUST)) for s in ("Python", "SQL")},
                test_p=test_p, test_spec=role if test_p is not None else None,
                open_invites=draw(st.integers(0, 6)))
    lcb = draw(st.floats(-0.2, 1.2))
    kind = draw(st.sampled_from((None, "profile", "other")))
    return need, base, lcb, kind


@settings(max_examples=3000, deadline=None, derandomize=True)
@given(cases())
def test_fsp_history_never_lowers_the_employer_score(case):
    need, base, lcb, kind = case
    without = score(need, CandidateFacts(fsp_lcb=None, **base))
    with_fsp = score(need, CandidateFacts(fsp_lcb=lcb, fsp_kind=kind, fsp_discipline="algorithmic", **base))
    assert with_fsp.employer + 1e-12 >= without.employer
    assert with_fsp.score + 1e-9 >= without.score
    assert with_fsp.fit == without.fit and with_fsp.tier == without.tier


@settings(max_examples=1500, deadline=None, derandomize=True)
@given(cases(), st.floats(0.0, 1.0), st.floats(0.0, 1.0))
def test_a_stronger_fsp_bound_never_ranks_lower(case, a, b):
    need, base, _, kind = case
    lo, hi = sorted((a, b))
    low = score(need, CandidateFacts(fsp_lcb=lo, fsp_kind=kind, **base))
    high = score(need, CandidateFacts(fsp_lcb=hi, fsp_kind=kind, **base))
    assert high.employer + 1e-12 >= low.employer


@settings(max_examples=1000, deadline=None, derandomize=True)
@given(cases())
def test_contributions_still_sum_to_the_employer_score(case):
    need, base, lcb, kind = case
    result = score(need, CandidateFacts(fsp_lcb=lcb, fsp_kind=kind, **base))
    parts = [f.contrib for f in result.factors if f.contrib is not None]
    assert abs(sum(parts) - result.employer) < 1e-9


def test_shipped_rule_is_boost():
    assert matching.FSP_LIFT == "boost"

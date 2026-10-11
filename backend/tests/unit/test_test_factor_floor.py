"""A passed test never scores below "not tested", at any probability, SE or age."""
from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.cat import PASS_P
from app.services.matching import UNTESTED, CandidateFacts, NeedSpec, score

NEED = NeedSpec(role="backend", grade="middle", skills=("Python",))


def _facts(**kw):
    base = dict(role="backend", grade="middle", grade_source="assessed", skills={"Python": "test_confirmed"},
                test_spec="backend")
    base.update(kw)
    return CandidateFacts(**base)


@settings(max_examples=200, deadline=None)
@given(p=st.floats(min_value=PASS_P, max_value=1.0), se=st.floats(min_value=0.01, max_value=1.0),
       days=st.integers(min_value=0, max_value=1500), n=st.integers(min_value=4, max_value=40))
def test_a_pass_is_never_below_untested(p, se, days, n):
    tested_at = datetime.now(UTC) - timedelta(days=days)
    facts = _facts(test_p=p, test_se=se, tested_at=tested_at, test_n=n, test_correct=int(n * 0.6))
    test = next(f for f in score(NEED, facts).factors if f.key == "test")
    assert test.value >= UNTESTED - 1e-9


def test_legacy_confirmation_without_probability_is_a_bare_pass():
    import inspect

    from app.services.search import pipeline
    assert "else (PASS_P if conf else None)" in inspect.getsource(pipeline)

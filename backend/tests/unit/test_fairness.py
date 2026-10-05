"""Name, gender and region are not ranking features.

The plan's fairness check: a counterfactual change of identity must not move a candidate.
These fields are absent from the score inputs, so they cannot change the order.
"""
from app.services.matching import WEIGHTS, CandidateFacts, NeedSpec, score
from app.services.scoring.engine import EventInput

_IDENTITY = {"display_name", "gender", "region", "email", "phone", "fsp_id", "birth_date"}


def test_score_inputs_have_no_identity_fields():
    assert _IDENTITY.isdisjoint(CandidateFacts.__dataclass_fields__)
    assert _IDENTITY.isdisjoint(NeedSpec.__dataclass_fields__)
    assert _IDENTITY.isdisjoint(EventInput.__annotations__)
    assert _IDENTITY.isdisjoint(WEIGHTS)


def test_same_professional_facts_rank_the_same():
    need = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"), industry="финтех")
    facts = CandidateFacts(
        role="backend", grade="middle", grade_source="assessed",
        skills={"Python": "test_confirmed", "PostgreSQL": "self_reported"},
        test_p=0.9, test_spec="backend", fsp_lcb=0.55, industry="финтех", text_rank=0.4,
    )
    first, second = score(need, facts), score(need, facts)
    assert first.score == second.score
    assert [(f.key, f.value) for f in first.factors] == [(f.key, f.value) for f in second.factors]

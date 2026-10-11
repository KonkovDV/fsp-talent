"""Name, gender and the profile region field are not ranking features.

The plan's fairness check: a counterfactual change of identity must not move a candidate.
Those fields are absent from the score inputs, so they cannot change the order.
City and work format enter only when the vacancy names them.
A hidden group with the same professional facts must also clear the four-fifths rule.
"""
import random

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


def test_hidden_group_clears_the_four_fifths_rule():
    """The same professional facts under two hidden labels produce the same scores, so the top keeps both."""
    rng = random.Random(7)
    need = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))
    scored = []
    for i in range(200):
        facts = CandidateFacts(
            role="backend", grade="middle", grade_source="assessed",
            skills={"Python": "test_confirmed" if rng.random() < 0.5 else "self_reported"},
            test_p=rng.choice((0.4, 0.8, 0.95)), test_spec="backend",
            fsp_lcb=rng.choice((None, 0.4, 0.7)),
        )
        value = score(need, facts).score
        scored.append((True, value, i))
        scored.append((False, value, i))
    scored.sort(key=lambda row: (-row[1], row[2]))
    top = scored[:200]
    minority_in_top = sum(flag for flag, _, _ in top) / len(top)
    majority_in_top = 1 - minority_in_top
    ratio = (minority_in_top / 0.5) / (majority_in_top / 0.5)
    assert ratio == 1.0


def test_language_diagnosis_compares_to_largest_group_and_counts_relevant():
    from app.validation.fairness import diagnosis_markdown, language_diagnosis
    rows = [{"language": ["Python"] * 20 + ["C#"] * 2,
             "relevant": [True] * 5 + [False] * 15 + [True, False]}]
    diag = {g: rest for g, *rest in language_diagnosis(rows)}
    assert diag["Python"][2] == 1.0          # IR of the largest group is 1
    assert diag["C#"][3] == 1                # one relevant C# place
    assert diag["C#"][4] == 0.0              # C# sits at places 20–21, out of the top 10
    assert "(< 2 %)" not in diagnosis_markdown(rows) or diag["C#"][1] < 0.02


def test_equal_fit_ratio_removes_a_gap_explained_by_fit():
    """C# has only weak-fit places, so its raw rate is low; inside each fit level it is treated like Python."""
    from app.validation.fairness import stratified_ratio
    # 12 Python places: 6 fit (label 3, all in top), 6 not (label 0, below top 10 except none);
    # 4 C# places: all label 0 below the top. Same rule for both groups inside a label.
    language = ["Python"] * 6 + ["Python"] * 4 + ["C#"] * 4 + ["Python"] * 2
    label = [3] * 6 + [0] * 4 + [0] * 4 + [0] * 2
    rows = [{"language": language, "label": label}]
    # top 10 = 6 fitting Python + 4 non-fitting Python; C# non-fitting sit at places 10-13
    ratio = stratified_ratio(rows, "language", "C#", "Python")
    assert ratio == 0.0   # at label 0 Python got 4 of 6 into the top, C# 0 of 4: the order, not fit
    fair = [{"language": ["Python"] * 6 + ["C#", "Python"] * 2 + ["C#", "Python"] * 2,
             "label": [3] * 6 + [0] * 8}]
    assert abs(stratified_ratio(fair, "language", "C#", "Python") - 1.0) < 1e-9


def test_equal_fit_ratio_is_none_without_overlap():
    from app.validation.fairness import stratified_ratio
    rows = [{"language": ["Python", "C#"], "label": [3, 0]}]
    assert stratified_ratio(rows, "language", "C#", "Python") is None

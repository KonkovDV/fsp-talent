"""A discipline result confirms a catalog skill. A measured miss stays a claim."""
from app.services.fsp_skills import granted_skills
from app.services.matching import CandidateFacts, NeedSpec, score


def _person(**kwargs) -> CandidateFacts:
    fields = {"role": "backend", "grade": "middle", "grade_source": "declared"}
    fields.update(kwargs)
    return CandidateFacts(**fields)


def test_a_prize_or_a_rank_confirms_the_discipline_skill():
    assert granted_skills([("algorithmic", 2, 20, False)], []) == frozenset({"Algorithms"})
    assert granted_skills([("algorithmic", 1, 20, True)], []) == frozenset()
    assert granted_skills([("algorithmic", 8, 20, False)], []) == frozenset()
    assert granted_skills([("algorithmic", 1, 5, False)], []) == frozenset()
    assert granted_skills([], ["security"]) == frozenset({"Pentesting"})
    assert granted_skills([("ai", 1, 30, False)], []) == frozenset({"Machine Learning"})
    assert granted_skills(
        [("product", 1, 40, False), ("robotics", 1, 40, False), ("bas", 1, 40, False)], ["product"],
    ) == frozenset()


def test_the_grant_outranks_a_claim_and_does_not_erase_a_miss():
    need = NeedSpec(role="backend", skills=("Algorithms",))
    claim = score(need, _person(skills={"Algorithms": "self_reported"}))
    lifted = score(need, _person(
        skills={"Algorithms": "self_reported"}, fsp_skills=frozenset({"Algorithms"})))
    assert lifted.score > claim.score
    assert any("Подтверждены ФСП" in line for line in lifted.plus)

    missed = score(need, _person(
        skills={"Algorithms": "self_reported"},
        tested_skills=frozenset({"Algorithms"}),
        fsp_skills=frozenset({"Algorithms"}),
    ))
    assert missed.score == claim.score
    assert not any("Подтверждены ФСП" in line for line in missed.plus)

    tested = score(need, _person(
        skills={"Algorithms": "test_confirmed"}, fsp_skills=frozenset({"Algorithms"})))
    assert any("Подтверждены тестом" in line for line in tested.plus)
    assert not any("Подтверждены ФСП" in line for line in tested.plus)

    without = score(need, _person(fsp_skills=frozenset({"Algorithms"})), use_fsp=False)
    bare = score(need, _person(), use_fsp=False)
    assert without.score == bare.score


def test_an_undeclared_skill_is_filled_from_the_registry():
    need = NeedSpec(skills=("Algorithms",))
    filled = score(need, _person(fsp_skills=frozenset({"Algorithms"})))
    empty = score(need, _person())
    assert filled.score > empty.score
    assert any("Algorithms" in line for line in filled.plus)

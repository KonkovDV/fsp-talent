"""Explainable match score and the offline ranking benchmark."""
from app.services.matching import CandidateFacts, NeedSpec, recommended_categories, score
from app.validation.matching import evaluate, make_dataset, relevance, sha256

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))


def _cand(**kw) -> CandidateFacts:
    base = dict(role="backend", grade="middle", grade_source="declared",
                skills={"Python": "self_reported", "PostgreSQL": "self_reported"})
    base.update(kw)
    return CandidateFacts(**base)


def test_tested_skills_and_grade_outrank_declared_ones():
    declared = score(NEED, _cand())
    tested = score(NEED, _cand(grade_source="assessed", test_p=0.95,
                               skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    assert tested.score > declared.score
    assert any("тестом" in line for line in tested.plus)


def test_no_fsp_history_is_neutral_not_a_penalty():
    without = score(NEED, _cand(fsp_lcb=None))
    weak_fsp = score(NEED, _cand(fsp_lcb=0.05))
    assert without.score > weak_fsp.score
    assert any("Нет истории ФСП" in line for line in without.info)
    assert next(f for f in without.factors if f.key == "fsp").value is None


def test_inapplicable_factors_are_reweighted():
    only_skills = NeedSpec(skills=("Python",))
    perfect = score(only_skills, _cand(skills={"Python": "test_confirmed"}, test_p=1.0, grade_source="assessed"))
    assert perfect.score > 0.95
    assert {f.key for f in perfect.factors if f.value is None} >= {"grade", "role", "text", "industry"}


def test_missing_skill_is_a_minus_and_related_tech_gets_partial_credit():
    mysql = score(NEED, _cand(skills={"Python": "self_reported", "MySQL": "self_reported"}))
    none = score(NEED, _cand(skills={"Python": "self_reported"}))
    assert mysql.score > none.score
    assert any("PostgreSQL ≈ MySQL" in line for line in mysql.info)
    assert any("PostgreSQL" in line for line in none.minus)


def test_wrong_role_and_lower_grade_cost_points():
    good = score(NEED, _cand())
    assert score(NEED, _cand(role="frontend")).score < score(NEED, _cand(role="fullstack")).score < good.score
    assert score(NEED, _cand(grade="junior")).score < good.score


def test_recommended_categories_pick_the_strongest_cells():
    cells = recommended_categories([("backend", "middle", 0.9), ("backend", "middle", 0.8), ("ml", "junior", 0.3)])
    assert cells[0]["role"] == "backend" and cells[0]["candidates"] == 2


def test_relevance_labels_follow_the_hidden_truth():
    need = {"role": "backend", "grade": "middle", "skills": ["Python", "SQL"]}
    assert relevance(need, {"role": "backend", "grade": "middle", "skills": ["Python", "SQL"]}) == 3
    assert relevance(need, {"role": "fullstack", "grade": "senior", "skills": ["Python", "SQL"]}) == 2
    assert relevance(need, {"role": "backend", "grade": "lead", "skills": ["Python"]}) == 1
    assert relevance(need, {"role": "ml", "grade": "middle", "skills": ["Python", "SQL"]}) == 0


def test_benchmark_is_deterministic_and_beats_the_baselines():
    data = make_dataset(400, 40, seed=2026)
    assert sha256(data) == sha256(make_dataset(400, 40, seed=2026))
    rows = {r.method: r for r in evaluate(data)}
    assert rows["full"].ndcg10 > rows["keyword"].ndcg10 > rows["random"].ndcg10

"""Explainable match score and the offline ranking benchmark."""
from app.services.matching import CandidateFacts, NeedSpec, anonymous_compare, recommended_categories, score
from app.services.search.pipeline import order_pool
from app.validation.matching import evaluate, load_pairs, make_dataset, relevance, sha256

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))


def _cand(**kw) -> CandidateFacts:
    base = dict(role="backend", grade="middle", grade_source="declared",
                skills={"Python": "self_reported", "PostgreSQL": "self_reported"})
    base.update(kw)
    return CandidateFacts(**base)


def test_confirmed_profile_outranks_the_same_declared_fit():
    """Same skills and grade: a passed test and FSP results sort first, without jumping a worse fit."""
    declared = score(NEED, _cand(test_p=0.4, grade_source="assessed",
                                 skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    confirmed = score(NEED, _cand(test_p=0.95, fsp_lcb=0.7, grade_source="assessed",
                                  skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    assert confirmed.score > declared.score
    assert confirmed.score - declared.score < 0.01
    resume = score(NEED, _cand())
    assert confirmed.score - resume.score >= 0.15


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


def test_testing_and_analytics_are_adjacent_to_backend():
    """A tester or an analyst is a neighbour of backend, not a foreign specialization."""
    same = score(NEED, _cand())
    tester = score(NEED, _cand(role="qa"))
    analyst = score(NEED, _cand(role="analyst"))
    foreign = score(NEED, _cand(role="embedded"))
    assert foreign.score < tester.score < same.score
    assert foreign.score < analyst.score < same.score
    assert any("Тестирование" in line for line in tester.info)
    assert any("Аналитика" in line for line in analyst.info)


def test_data_engineering_is_adjacent_to_backend():
    same = score(NEED, _cand())
    engineer = score(NEED, _cand(role="data"))
    foreign = score(NEED, _cand(role="embedded"))
    assert foreign.score < engineer.score < same.score
    assert any("Инженерия данных" in line for line in engineer.info)


def test_category_percentile_counts_only_the_others():
    from app.services.matching import category_percentile
    assert category_percentile(0.9, [0.1, 0.2, 0.4, 0.8]) == 100
    assert category_percentile(0.3, [0.1, 0.2, 0.4, 0.9]) == 50
    assert category_percentile(0.5, []) is None


def test_compare_stays_anonymous():
    from app.services.matching import anonymous_compare
    cards = [{"candidate_id": "a", "role": "backend", "grade": "middle", "display_name": "Иван",
              "fsp_id": "FSP1", "match": {"score": 0.8, "factors": [], "plus": ["Тест"], "minus": []}}]
    rows = anonymous_compare(cards, ["a", "missing"])
    assert len(rows) == 1
    assert rows[0]["score"] == 0.8
    assert "display_name" not in rows[0] and "fsp_id" not in rows[0]


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


def test_explanation_carries_stable_codes():
    scored = score(NEED, _cand(grade_source="assessed", test_p=0.9, fsp_lcb=None,
                               skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    codes = {r.code for r in scored.reasons}
    assert {"VERIFIED_SKILL", "TEST_SCORE", "FSP_NEUTRAL", "CATEGORY_MATCH"} <= codes
    gap = score(NEED, _cand(skills={"Python": "self_reported"}))
    assert any(r.code == "SKILL_GAP" for r in gap.reasons)
    neighbour = score(NEED, _cand(role="qa"))
    assert any(r.code == "RELATED_ROLE" for r in neighbour.reasons)


def test_missing_fsp_does_not_change_the_score_when_the_axis_is_off():
    plain = score(NEED, _cand(fsp_lcb=None))
    assert plain.score == score(NEED, _cand(fsp_lcb=None), use_fsp=False).score


def test_pages_keep_the_order_of_the_full_list():
    scores = {"a": 0.2, "b": 0.9, "c": 0.5, "d": 0.9}
    fused = {"a": 0.1, "b": 0.0, "c": 0.4, "d": 0.2}
    best = {key: 0.0 for key in scores}
    full = order_pool(list(scores), scores, fused, best)
    assert order_pool(full[:2], scores, fused, best) == full[:2]
    assert full[:2] + full[2:] == full


def test_compare_omits_a_candidate_who_is_not_in_the_list():
    cards = [{"candidate_id": "a", "match": {"plus": [], "minus": [], "factors": [], "reasons": []}}]
    assert len(anonymous_compare(cards, ["a", "b"])) == 1


def test_jury_pairs_file_is_scored(tmp_path):
    path = tmp_path / "pairs.jsonl"
    observed = {"role": "backend", "grade": "middle", "grade_source": "assessed",
                "skills": {"Python": "test_confirmed"}, "test_p": 0.9, "fsp_lcb": None, "industry": "fintech"}
    rows = []
    for i, label in enumerate((3, 1, 0)):
        rows.append({"need": {"id": "n", "role": "backend", "grade": "middle", "skills": ["Python"]},
                     "candidate": {"id": f"c{i}", "observed": observed}, "label": label})
    path.write_text("\n".join(__import__("json").dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    data = load_pairs(str(path))
    assert data["labels"]["n"]["c0"] == 3
    assert any(row.method == "full" for row in evaluate(data))


def test_empty_need_ranks_by_profile_strength_not_a_near_zero_fit():
    """No criteria: the score must not collapse to ~0.01 (it was shown as «1 из 100»)."""
    from app.services.matching import CandidateFacts, NeedSpec, score
    strong = score(NeedSpec(), CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                                              skills={}, test_p=0.95, test_spec="backend", fsp_lcb=0.6))
    weak = score(NeedSpec(), CandidateFacts(role="backend", grade="middle", grade_source="declared",
                                            skills={}, test_p=None, test_spec=None, fsp_lcb=None))
    assert strong.basis == "evidence" and strong.score > 0.5
    assert strong.score > weak.score
    fitted = score(NeedSpec(role="backend"), CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                                                            skills={}, test_p=0.95, test_spec="backend", fsp_lcb=0.6))
    assert fitted.basis == "fit"

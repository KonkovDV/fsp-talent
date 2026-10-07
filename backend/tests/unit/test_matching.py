"""Explainable match score and the offline ranking benchmark."""
import random

from app.services.matching import (
    CandidateFacts,
    NeedSpec,
    anonymous_compare,
    reason_source,
    recommended_categories,
    score,
    skill_counterfactual,
    wilson_lower,
)
from app.services.search.pipeline import order_pool
from app.validation.matching import (
    blind_kappa,
    blind_label,
    cohen_kappa,
    evaluate,
    load_pairs,
    make_dataset,
    relevance,
    sha256,
)

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


def test_salary_changes_rank_only_when_both_sides_named_a_band():
    plain = score(NEED, _cand())
    wish_only = score(NEED, _cand(salary_from=200_000, salary_to=280_000))
    assert wish_only.score == plain.score
    covered_need = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"),
                            salary_from=180_000, salary_to=260_000)
    covered = score(covered_need, _cand(salary_from=200_000, salary_to=280_000))
    assert any(r.code == "PAY_FIT" for r in covered.reasons)
    short = score(NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"),
                           salary_from=100_000, salary_to=140_000),
                  _cand(salary_from=200_000, salary_to=280_000))
    assert short.score < plain.score
    assert any(r.code == "PAY_GAP" for r in short.reasons)


def test_pay_counterfactual_starts_at_five_named_wishes():
    from app.services.matching import pay_counterfactual
    need = NeedSpec(salary_from=150_000, salary_to=200_000)
    assert pay_counterfactual(need, [_cand(salary_from=250_000) for _ in range(4)]) is None
    hint = pay_counterfactual(need, [_cand(salary_from=220_000) for _ in range(6)])
    assert hint is not None
    assert hint["gained"] >= 1 and hint["proposed_to"] > 200_000


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


def test_wilson_on_the_answer_count_lowers_the_test_factor():
    point = score(NEED, _cand(test_p=0.9, grade_source="assessed"))
    counted = score(NEED, _cand(test_p=0.9, test_correct=9, test_n=12, grade_source="assessed"))
    assert counted.score < point.score
    assert any("нижняя граница" in line for line in counted.plus)


def test_lower_bound_and_queue_do_not_touch_a_profile_without_those_signals():
    plain = score(NEED, _cand(test_p=0.9, grade_source="assessed"))
    bounded = score(NEED, _cand(test_p=0.9, test_se=0.3, grade_source="assessed"))
    assert bounded.score < plain.score
    assert any("нижняя граница" in line for line in bounded.plus)
    assert score(NEED, _cand(open_invites=0)).score == score(NEED, _cand()).score
    busy = score(NEED, _cand(open_invites=5))
    assert busy.score < score(NEED, _cand()).score
    assert any(r.code == "CONGESTION" for r in busy.reasons)
    assert reason_source("TEST_SCORE") == "тест"
    assert reason_source("CONGESTION") == "очередь"


def test_a_past_pay_refusal_lowers_acceptance_only_together_with_a_named_band():
    band = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"),
                    salary_from=180_000, salary_to=260_000)
    calm = score(band, _cand(salary_from=200_000))
    refused = score(band, _cand(salary_from=200_000, salary_refusals=1))
    assert refused.score < calm.score
    assert any(r.code == "SALARY_HISTORY" for r in refused.reasons)
    assert score(NEED, _cand(salary_refusals=2)).score == score(NEED, _cand()).score


def test_skill_counterfactual_names_the_only_missing_skill():
    people = [_cand(skills={"Python": "self_reported"}) for _ in range(5)]
    hint = skill_counterfactual(NEED, people)
    assert hint is not None and hint["skill"] == "PostgreSQL" and hint["gained"] == 5
    assert skill_counterfactual(NEED, people[:4]) is None


def test_an_untested_candidate_takes_the_last_seat_of_a_close_block():
    scores = {f"t{i}": 1.0 - i * 0.001 for i in range(10)}
    scores["cold"] = scores["t9"] - 0.05
    fused = {key: 0.0 for key in scores}
    best = {key: 0.0 for key in scores}
    ordered = order_pool(list(scores), scores, fused, best, {"cold"})
    assert ordered[9] == "cold"
    scores["cold"] = 0.999
    stayed = order_pool(list(scores), scores, fused, best, {"cold"})
    assert stayed.index("cold") == 1


def test_blind_rater_uses_its_own_seed_and_not_the_hidden_truth():
    assert cohen_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    assert cohen_kappa([0, 0, 1, 1], [0, 1, 0, 1]) < 1.0
    data = make_dataset(30, 4, seed=3)
    digest = sha256(data)
    first = blind_kappa(data, seed=99)
    assert sha256(data) == digest
    assert -1.0 <= first < 1.0
    assert blind_kappa(data, seed=99) == first
    assert blind_kappa(data, seed=100) != first
    need = data["needs"][0]
    observed = data["candidates"][0]["observed"]
    assert blind_label(need, observed, random.Random(1)) == blind_label(need, dict(observed), random.Random(1))


def test_wilson_bounds_a_share_and_is_not_a_rank_input():
    assert wilson_lower(0, 0) is None
    low = wilson_lower(8, 10)
    assert low is not None and 0.4 < low < 0.8
    assert wilson_lower(0, 10) == 0.0


def test_compare_keeps_four_cards():
    cards = [{"candidate_id": str(i), "role": "backend", "grade": "middle",
              "match": {"factors": [], "reasons": []}} for i in range(5)]
    assert len(anonymous_compare(cards, [str(i) for i in range(5)])) == 4

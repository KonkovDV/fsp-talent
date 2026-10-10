"""Explainable match score and the offline ranking benchmark."""
import random

from app.services import matching as matching_mod
from app.services.matching import (
    CandidateFacts,
    NeedSpec,
    _harmonic,
    anonymous_compare,
    reason_source,
    recommended_categories,
    score,
    skill_counterfactual,
    wilson_lower,
)
from app.services.search.pipeline import order_pool
from app.validation.matching import (
    blind_candidate_ids,
    blind_kappa,
    blind_label,
    cohen_kappa,
    evaluate,
    load_pairs,
    make_dataset,
    merge_rater_labels,
    paired_report,
    quadratic_weighted_kappa,
    rank,
    relevance,
    sha256,
    sign_permutation,
    write_blind_sheet,
)

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))


def _cand(**kw) -> CandidateFacts:
    base = dict(role="backend", grade="middle", grade_source="declared",
                skills={"Python": "self_reported", "PostgreSQL": "self_reported"})
    base.update(kw)
    return CandidateFacts(**base)


def test_confirmed_profile_outranks_the_same_declared_fit():
    """Same skills and grade: a stronger test and FSP results sort first by a visible margin."""
    weak = score(NEED, _cand(test_p=0.4, grade_source="assessed",
                             skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    confirmed = score(NEED, _cand(test_p=0.95, fsp_lcb=0.7, grade_source="assessed",
                                  skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    assert confirmed.score - weak.score >= 0.05
    resume = score(NEED, _cand())
    assert confirmed.score - resume.score >= 0.15


def test_inside_the_category_a_declared_skill_does_not_outweigh_the_test():
    """Three required skills: one more self-described skill loses to a confirmed grade with a strong test."""
    need = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL", "Docker"))
    resume = score(need, _cand(skills={"Python": "self_reported", "PostgreSQL": "self_reported",
                                       "Docker": "self_reported"}))
    tested = score(need, _cand(grade_source="assessed", test_p=0.9,
                               skills={"Python": "self_reported", "PostgreSQL": "self_reported"}))
    assert tested.score > resume.score


def test_confirmed_grade_outranks_declared_grade_at_the_same_skills():
    declared = score(NEED, _cand(fsp_lcb=0.5))
    assessed = score(NEED, _cand(fsp_lcb=0.5, grade_source="assessed", test_p=0.8))
    assert assessed.score > declared.score


def test_evidence_does_not_pull_another_category_over_a_matching_one():
    """A strong frontend profile with the same skills stays below an untested backend candidate."""
    matching = score(NEED, _cand())
    other = score(NEED, _cand(role="frontend", grade_source="assessed", test_p=0.99, fsp_lcb=0.9,
                              skills={"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    assert matching.score > other.score


def test_test_and_fsp_lines_carry_their_contribution():
    m = score(NEED, _cand(grade_source="assessed", test_p=0.9, fsp_lcb=0.2))
    points = {r.code: r.points for r in m.reasons if r.points is not None}
    assert set(points) == {"TEST_SCORE", "FSP_SCORE"}
    assert points["TEST_SCORE"] > points["FSP_SCORE"] > 0


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
    rows = [("backend", "middle", 0.9)] * 5 + [("backend", "middle", 0.8)]
    rows += [("ml", "junior", 0.99), ("ml", "junior", 0.3)]
    cells = recommended_categories(rows)
    assert cells[0]["role"] == "backend" and cells[0]["candidates"] == 6
    assert all(cell["candidates"] >= 5 for cell in cells)


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


def test_quadratic_kappa_penalises_a_far_miss_more_than_a_near_one():
    same = [0, 1, 2, 3, 0, 1, 2, 3]
    assert quadratic_weighted_kappa(same, same) == 1.0
    near = quadratic_weighted_kappa(same, [0, 1, 2, 3, 1, 2, 3, 3])
    far = quadratic_weighted_kappa(same, [3, 2, 1, 0, 3, 2, 1, 0])
    assert far < near < 1.0


def test_blind_sheet_hides_the_truth_and_mixes_the_two_tops(tmp_path):
    dataset = make_dataset(40, 2, seed=4)
    need = dataset["needs"][0]
    ids = blind_candidate_ids(dataset, need, random.Random(5))
    assert len(ids) == len(set(ids)) == 8
    model = rank(dataset, need, "full", random.Random(0))
    keyword = rank(dataset, need, "keyword", random.Random(0))
    assert set(model[:3]) <= set(ids)
    taken = []
    for cid in keyword:
        if cid in model[:3]:
            continue
        taken.append(cid)
        if len(taken) == 3:
            break
    assert set(taken) <= set(ids)
    path = tmp_path / "sheet.csv"
    write_blind_sheet(dataset, str(path), 8, random.Random(5))
    text = path.read_text(encoding="utf-8-sig")
    assert "theta" not in text and "балл" not in text.lower()
    key = (tmp_path / "sheet.key.json").read_text(encoding="utf-8")
    assert "theta" not in key and "truth" not in key
    assert text.splitlines()[0] == "pair_id,need,candidate_card,label"


def test_merged_labels_use_the_floor_of_the_mean():
    key = {"pairs": [{"pair_id": "p001", "need": {"id": "n", "role": "backend", "grade": "middle",
                                                  "skills": ["Python"]},
                      "candidate_id": "c1", "observed": {"role": "backend", "grade": "middle"}}]}
    lines = merge_rater_labels({"p001": 3}, {"p001": 2}, key)
    assert lines[0]["label"] == 2
    assert merge_rater_labels({"p001": 3}, {"p001": 0}, key)[0]["label"] == 1


def test_a_labelled_handful_is_not_ranked_against_the_rest_of_the_bank():
    dataset = make_dataset(12, 1, seed=2)
    need = dataset["needs"][0]
    only = dataset["candidates"][0]["id"]
    dataset["labels"] = {need["id"]: {only: 3}}
    rows = {row.method: row for row in evaluate(dataset)}
    assert rows["full"].ndcg10 == 1.0


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


def test_the_demo_ceiling_hints_when_wishes_straddle_it():
    from app.services.matching import pay_counterfactual
    need = NeedSpec(salary_from=180_000, salary_to=260_000)
    people = [_cand(salary_from=amount) for amount in (220_000, 240_000, 280_000, 285_000, 290_000)]
    hint = pay_counterfactual(need, people)
    assert hint is not None and hint["known"] >= 5 and hint["gained"] >= 1


def test_reply_outlook_is_shown_apart_from_the_score():
    """The chance they answer is for the invite button. It does not move the score."""
    from app.services.matching import reply_outlook
    need = NeedSpec(role="backend", salary_from=200_000, salary_to=280_000,
                    work_format="remote", city="Казань")
    keen = _cand(salary_from=220_000, salary_to=260_000, work_formats=("remote",),
                 city="Казань", job_search="active")
    cold = _cand(salary_from=400_000, work_formats=("office",), city="Москва", job_search="open")
    high = reply_outlook(need, keen)
    low = reply_outlook(need, cold)
    assert high is not None and high["label"] == "высокая" and high["p"] >= 0.7
    assert low is not None and low["label"] == "низкая" and low["p"] < high["p"]
    unnamed = reply_outlook(need, _cand(salary_from=220_000, work_formats=("remote",),
                                         city=None, job_search="active"))
    assert unnamed is not None and unnamed["p"] > low["p"]
    assert reply_outlook(NeedSpec(role="backend"), keen) is None
    ranked = score(need, keen).score
    reply_outlook(need, keen)
    assert score(need, keen).score == ranked


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


def test_open_to_offers_lowers_the_chance_of_accepting():
    band = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"),
                    salary_from=180_000, salary_to=260_000)
    person = dict(salary_from=200_000, salary_to=280_000)
    active = score(band, _cand(job_search="active", **person))
    opened = score(band, _cand(job_search="open", **person))
    assert opened.score < active.score
    assert any(r.code == "JOB_SEARCH_ACTIVE" for r in active.reasons)
    assert any(r.code == "JOB_SEARCH_OPEN" for r in opened.reasons)
    assert any(r.code == "PAY_FIT" for r in opened.reasons)
    quiet = score(NEED, _cand(job_search="open"))
    busy = score(NEED, _cand(job_search="active"))
    assert quiet.score == busy.score


def test_not_looking_stays_out_of_search_without_withdrawing_consent():
    from app.models.participant import Participant
    person = Participant(is_visible=True, is_minor=False, job_search="not_looking")
    assert person.is_visible and not person.discoverable
    listed = Participant(is_visible=True, is_minor=False, job_search="open")
    assert listed.discoverable


def test_not_looking_refuses_an_invitation(monkeypatch):
    import asyncio
    import uuid
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.v1.offers import OfferCreate, _create_offer
    from app.models.participant import Participant

    async def quiet(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.api.v1.offers.too_many", quiet)
    employer_id = uuid.uuid4()
    candidate = Participant(is_visible=True, is_minor=False, job_search="not_looking")

    class _Db:
        async def get(self, model, _id):
            if model.__name__ == "Employer":
                return SimpleNamespace(id=employer_id)
            return candidate

    body = OfferCreate(
        candidate_id=uuid.uuid4(), salary_from_gross=100_000, salary_to_gross=150_000,
        role="backend", contact_method="почта",
    )
    try:
        asyncio.run(_create_offer(body, {"sub": str(employer_id)}, _Db()))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Кандидат недоступен для предложений"
        return
    raise AssertionError("приглашение прошло")


def test_seed_splits_job_search_forty_fortyfive_fifteen():
    import random
    from collections import Counter

    from seed.generate_seed import job_search_of

    rng = random.Random(1)
    counts = Counter(job_search_of(rng) for _ in range(20_000))
    assert abs(counts["active"] / 20_000 - 0.40) < 0.02
    assert abs(counts["open"] / 20_000 - 0.45) < 0.02
    assert abs(counts["not_looking"] / 20_000 - 0.15) < 0.02


def test_search_sql_skips_people_who_are_not_looking():
    from sqlalchemy import literal
    from sqlalchemy.dialects import postgresql

    from app.services.search.pipeline import _in_search
    sql = str(_in_search(literal(True)).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "job_search" in sql and "not_looking" in sql
    assert "grade_source" in sql and "declared" in sql and "assessed" in sql


def test_confirmed_grade_outranks_declared_grade_inside_one_tier(monkeypatch):
    """Same skills, same tier: a passed test stays above a declared grade even with a lower score."""
    monkeypatch.setattr("app.services.matching.FIT_TIER_DELTA", 0.10)
    declared = score(NEED, _cand(grade_source="declared"))
    assessed = score(NEED, _cand(grade_source="assessed", test_p=0.9))
    assert declared.tier == assessed.tier
    ordered = order_pool(
        ["declared", "assessed"],
        {"declared": 0.99, "assessed": 0.10}, {}, {},
        tiers={"declared": declared.tier, "assessed": assessed.tier},
        confirmed={"declared": 0, "assessed": 1},
        fits={"declared": declared.fit, "assessed": assessed.fit})
    assert ordered[0] == "assessed"


def test_a_lower_tier_cannot_overtake_with_a_test():
    weak = score(NEED, _cand(skills={}))
    strong = score(NEED, _cand())
    assert weak.tier is not None and strong.tier is not None and weak.tier < strong.tier
    ordered = order_pool(
        ["weak", "strong"],
        {"weak": 0.99, "strong": 0.01}, {}, {},
        tiers={"weak": weak.tier, "strong": strong.tier},
        confirmed={"weak": 1, "strong": 0},
        fits={"weak": weak.fit or 0.0, "strong": strong.fit or 0.0})
    assert ordered[0] == "strong"


def test_fsp_never_lowers_score():
    """The rejected boost (FSP only raises evidence) has the property. It is not the shipped score."""
    rng = random.Random(3001)
    previous_lift = matching_mod.FSP_LIFT
    matching_mod.FSP_LIFT = "boost"
    try:
        _assert_fsp_boost_never_lowers(rng)
    finally:
        matching_mod.FSP_LIFT = previous_lift


def _assert_fsp_boost_never_lowers(rng: random.Random) -> None:
    roles = ("backend", "frontend", "ml", "qa")
    grades = ("junior", "middle", "senior")
    previous = None
    ladder = None
    for i in range(2000):
        role = rng.choice(roles)
        grade = rng.choice(grades)
        need = NeedSpec(role=role, grade=grade, skills=("Python",))
        base = dict(role=role, grade=grade, grade_source=rng.choice(("declared", "assessed")),
                    skills={"Python": rng.choice(("self_reported", "test_confirmed"))},
                    test_p=rng.random() if rng.random() < 0.7 else None)
        if base["test_p"] is not None:
            base["test_spec"] = role
        plain = score(need, CandidateFacts(fsp_lcb=None, **base))
        x = rng.random() * 0.9
        lifted = score(need, CandidateFacts(fsp_lcb=x, **base))
        assert lifted.score + 1e-9 >= plain.score
        if i == 0:
            ladder = [score(need, CandidateFacts(fsp_lcb=step / 20, **base)).score for step in range(19)]
            previous = ladder
    assert previous == sorted(previous)
    assert ladder[0] <= ladder[-1]


def test_missing_fsp_does_not_change_the_fit_tier():
    without = score(NEED, _cand(fsp_lcb=None))
    with_fsp = score(NEED, _cand(fsp_lcb=0.8))
    assert without.fit == with_fsp.fit
    assert without.tier == with_fsp.tier
    assert without.score <= with_fsp.score


def test_contributions_sum_to_the_employer_score():
    rng = random.Random(3001)
    roles = ("backend", "frontend", "ml")
    grades = ("junior", "middle", "senior")
    for _ in range(2000):
        role = rng.choice(roles)
        grade = rng.choice(grades)
        need = NeedSpec(role=role, grade=grade, skills=("Python",),
                        salary_from=150_000 if rng.random() < 0.7 else None,
                        salary_to=220_000 if rng.random() < 0.7 else None)
        facts = CandidateFacts(
            role=role, grade=grade,
            grade_source=rng.choice(("declared", "assessed")),
            skills={"Python": rng.choice(("self_reported", "test_confirmed"))},
            test_p=rng.random() if rng.random() < 0.6 else None,
            test_spec=role,
            fsp_lcb=rng.random() * 0.8 if rng.random() < 0.5 else None,
            salary_from=180_000 if rng.random() < 0.6 else None,
            open_invites=rng.choice((0, 0, 3, 6)),
        )
        result = score(need, facts)
        parts = [f.contrib for f in result.factors if f.contrib is not None]
        assert abs(sum(parts) - result.employer) < 1e-9
        combined = result.employer if result.accept is None else _harmonic(result.employer, result.accept)
        expected = max(0.0, combined - result.congestion)
        assert abs(round(expected, 4) - result.score) < 1e-9


def test_a_cold_seat_is_named_on_the_card():
    from app.services.search.pipeline import PoolMatch, _match_body

    body = _match_body(PoolMatch(0.5, [], [], [], [], None), True)
    assert body["reasons"][0]["code"] == "COLD_SEAT"
    assert "без теста" in body["reasons"][0]["text"]


def test_sign_permutation_is_certain_only_for_a_zero_gap():
    quiet, _, _, certain = sign_permutation([0.2, -0.2, 0.1, -0.1], seed=1, rounds=300)
    assert abs(quiet) < 1e-12 and certain == 1.0
    mean, low, _, rare = sign_permutation([0.04] * 30, seed=2, rounds=400)
    assert mean == 0.04 and low > 0 and rare < 0.05
    text = paired_report([1], 40, 6)
    assert "Δ nDCG@10" in text and "нуль релевантных" in text


def test_a_passed_grade_is_not_under_an_unchecked_one():
    from app.services.matching import PASS_FLOOR, UNTESTED
    rng = random.Random(11)
    roles = ("backend", "frontend", "ml")
    grades = ("junior", "middle", "senior")
    saved = matching_mod.PASS_TEST_FLOOR
    matching_mod.PASS_TEST_FLOOR = True
    try:
        for _ in range(2000):
            role = rng.choice(roles)
            grade = rng.choice(grades)
            need = NeedSpec(role=role, grade=grade, skills=("Python",))
            facts = CandidateFacts(
                role=role, grade=grade, grade_source="assessed",
                skills={"Python": "test_confirmed"},
                test_p=rng.random(), test_spec=role,
                test_correct=rng.randint(0, 12), test_n=12,
            )
            result = score(need, facts)
            measured = next(factor.value for factor in result.factors if factor.key == "test")
            assert measured is not None and measured > UNTESTED
            assert measured + 1e-9 >= PASS_FLOOR
    finally:
        matching_mod.PASS_TEST_FLOOR = saved


def test_compare_keeps_four_cards():
    cards = [{"candidate_id": str(i), "role": "backend", "grade": "middle",
              "match": {"factors": [], "reasons": []}} for i in range(5)]
    assert len(anonymous_compare(cards, [str(i) for i in range(5)])) == 4


def test_city_and_format_raise_the_score_only_when_the_need_names_them():
    """A matching city and format score above a mismatch. An unnamed city is not a zero."""
    quiet = NeedSpec(role="backend", grade="middle", skills=("Python",))
    moscow = _cand(grade_source="assessed", skills={"Python": "test_confirmed"},
                   city="Москва", work_formats=("remote",))
    kazan = _cand(grade_source="assessed", skills={"Python": "test_confirmed"},
                  city="Казань", work_formats=("office",))
    blank = _cand(grade_source="assessed", skills={"Python": "test_confirmed"})
    assert score(quiet, moscow).score == score(quiet, kazan).score == score(quiet, blank).score

    named = NeedSpec(role="backend", grade="middle", skills=("Python",),
                     city="Москва", work_format="remote")
    same = score(named, moscow)
    other = score(named, kazan)
    unnamed = score(named, _cand(grade_source="assessed", skills={"Python": "test_confirmed"},
                                 work_formats=("remote",)))
    hybrid = score(named, _cand(grade_source="assessed", skills={"Python": "test_confirmed"},
                                city="Москва", work_formats=("hybrid",)))
    assert same.score > hybrid.score > other.score
    assert unnamed.score == same.score
    assert any(line.startswith("Город совпадает") for line in same.plus)
    assert any("Другой город" in line for line in other.minus)
    assert any("не штрафуется" in line for line in unnamed.info)

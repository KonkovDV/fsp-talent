"""The simulation runs end to end and its headline numbers stay inside agreed bounds."""
import random

from app.models.assessment import GRADE_ORDER
from app.services.matching import score
from app.services.search.pipeline import order_pool
from app.validation.assessment import Truth, _path_detail_lines, run, simulate_path, study_paths
from app.validation.matching import _facts, _spec, make_dataset, rank, sha256


def test_assessment_validation_bounds():
    r = run(n=250, seed=3, extras=False)
    assert r.clean.accuracy_clear > 0.80        # clear cases (> 0.5 from the cut) are classified right
    assert r.clean.false_pass < 0.15            # overclaimers rarely pass
    assert r.clean.false_recommend < 0.04
    assert r.guesser_pass < 0.02
    assert r.clean.mean_len <= 20
    assert r.clean.concept_share <= 0.30


def test_matching_rank_follows_the_product_order(monkeypatch):
    dataset = make_dataset(24, 1, seed=3)
    need = dataset["needs"][0]
    spec = _spec(need)
    scores, best, cold, ids = {}, {}, set(), []
    tiers, confirmed, fits = {}, {}, {}
    for candidate in dataset["candidates"]:
        facts = _facts(candidate)
        cid = candidate["id"]
        ids.append(cid)
        result = score(spec, facts)
        scores[cid] = result.score
        best[cid] = facts.fsp_lcb or 0.0
        tiers[cid] = result.tier or 0
        confirmed[cid] = result.confirmed
        fits[cid] = result.fit or 0.0
        if facts.test_n is None:
            cold.add(cid)
    assert rank(dataset, need, "full", random.Random(0)) == order_pool(ids, scores, {}, best, cold)
    monkeypatch.setattr("app.services.matching.USE_FIT_TIERS", True)
    assert rank(dataset, need, "full", random.Random(0)) == order_pool(
        ids, scores, {}, best, cold, tiers=tiers, confirmed=confirmed, fits=fits)
    bare = [cid for cid, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
    assert rank(dataset, need, "no_quota", random.Random(0)) == bare


def test_path_detail_splits_the_same_people_and_interpolates_the_half():
    from app.validation.assessment import path_detail

    # Middle cut is -0.5. Lower half of that grade is θ − cut < 0.5.
    rows = [
        (-0.4, "middle", "junior", False),
        (-0.2, "middle", "middle", False),
        (0.2, "middle", "middle", True),
        (0.0, "junior", None, False),
    ]
    detail = path_detail(rows)
    assert (detail["lower_n"], detail["lower_under"]) == (2, 0.5)
    assert (detail["upper_n"], detail["upper_under"]) == (2, 0.0)
    assert detail["equal_n"] == 3 and detail["below_n"] == 1
    assert abs(detail["half_shift"] - 0.375) < 1e-9
    truth = Truth.draw(random.Random(1))
    study = study_paths([(0.2, "backend", "middle"), (-0.8, "backend", "junior")], truth, random.Random(4), None)
    text = "\n".join(_path_detail_lines(study))
    assert study.n == 2 and "Нижняя" in text and "θ − порог" in text


def test_the_grade_path_stops_within_four_sessions():
    truth = Truth.draw(random.Random(1))
    high = simulate_path(2.5, "backend", "junior", truth, random.Random(2), None)
    low = simulate_path(-3.0, "backend", "lead", truth, random.Random(3), None)
    grade, sessions, _items, _passed = high
    assert sessions <= 4 and grade in GRADE_ORDER
    grade, sessions, _items, _passed = low
    assert sessions <= 4
    assert grade is None or GRADE_ORDER.index(grade) <= GRADE_ORDER.index("junior")


def test_overclaim_zero_states_the_true_grade_and_the_default_dataset_is_unchanged():
    honest = make_dataset(30, 4, seed=5, overclaim=0.0)
    assert all(c["observed"]["grade"] == c["truth"]["grade"] for c in honest["candidates"])
    assert sha256(make_dataset(40, 6, seed=9)) == sha256(make_dataset(40, 6, seed=9, overclaim=None))

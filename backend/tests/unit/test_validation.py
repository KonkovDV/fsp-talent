"""The simulation runs end to end and its headline numbers stay inside agreed bounds."""
import random
import sys

from app.models.assessment import GRADE_ORDER
from app.services.matching import score
from app.services.search.pipeline import order_pool
from app.validation.assessment import Session as SimSession
from app.validation.assessment import (
    Truth,
    _decision_consistency,
    _path_detail_lines,
    cohort,
    multiclass_rudner,
    population,
    reliability_curve,
    run,
    sh_holdout,
    sh_step,
    simulate_path,
    study_paths,
)
from app.validation.matching import _facts, _spec, make_dataset, overrated_parts, overrated_share, rank, sha256


def test_sympson_hetter_step_shrinks_an_overexposed_key():
    assert sh_step(1.0, 0.8, 0.40) == 0.5
    assert sh_step(0.5, 0.1, 0.40) == 1.0
    assert sh_step(0.4, 0.0, 0.40) == 0.4
    people = population(8, random.Random(1))
    truth = Truth.draw(random.Random(2))
    _, sessions = cohort(people, truth, random.Random(3), by_spec=True, control={"py_eval:3": 0.3})
    assert len(sessions) == 8
    # The holdout command is the record of a rejected experiment. A tiny cohort only executes it.
    assert sh_holdout(12) in (True, False)


def test_assessment_validation_bounds():
    r = run(n=250, seed=3, extras=False)
    assert r.clean.accuracy_clear > 0.80        # clear cases (> 0.5 from the cut) are classified right
    assert r.clean.false_pass < 0.15            # overclaimers rarely pass
    assert r.clean.false_recommend < 0.04
    assert r.guesser_pass < 0.02
    assert r.clean.mean_len <= 20
    assert r.clean.concept_share <= 0.30


def test_matching_rank_follows_the_product_order(monkeypatch):
    people = {
        "a": {"observed": {"grade": "senior", "grade_source": "declared"}, "truth": {"grade": "middle"}},
        "b": {"observed": {"grade": "senior", "grade_source": "assessed"}, "truth": {"grade": "middle"}},
        "c": {"observed": {"grade": "middle", "grade_source": "declared"}, "truth": {"grade": "middle"}},
    }
    assert overrated_share(["a", "b", "c"], people, k=3) == 2 / 3
    assert overrated_parts(["a", "b", "c"], people, k=3) == (1 / 3, 1 / 3)

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


def test_decision_consistency_follows_the_pass_rule():
    sure = SimSession("backend", "middle", 2.0, "middle", True, None, 12, [],
                      theta_hat=2.0, se=0.4, p_pass=0.99)
    weak = SimSession("backend", "middle", -0.4, None, False, None, 12, [],
                      theta_hat=-0.4, se=0.4, p_pass=0.2)
    assert _decision_consistency([sure]) > 0.9
    assert multiclass_rudner([sure]) > 0.5
    ece, rows = reliability_curve([sure, weak])
    assert len(rows) == 10 and 0 <= ece <= 1


def test_the_grade_path_stops_within_four_sessions():
    truth = Truth.draw(random.Random(1))
    high = simulate_path(2.5, "backend", "junior", truth, random.Random(2), None)
    low = simulate_path(-3.0, "backend", "lead", truth, random.Random(3), None)
    grade, sessions, _items, _passed = high
    assert sessions <= 4 and grade in GRADE_ORDER
    grade, sessions, _items, _passed = low
    assert sessions <= 4
    assert grade is None or GRADE_ORDER.index(grade) <= GRADE_ORDER.index("junior")


def test_matching_check_prints_the_paired_comparison(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["matching", "--seeds", "1", "--candidates", "60", "--needs", "6"])
    from app.validation.matching import main
    main()
    assert "Парное сравнение" in capsys.readouterr().out


def test_overclaim_zero_states_the_true_grade_and_the_default_dataset_is_unchanged():
    honest = make_dataset(30, 4, seed=5, overclaim=0.0)
    assert all(c["observed"]["grade"] == c["truth"]["grade"] for c in honest["candidates"])
    assert sha256(make_dataset(40, 6, seed=9)) == sha256(make_dataset(40, 6, seed=9, overclaim=None))

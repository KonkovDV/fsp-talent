"""The simulation runs end to end and its headline numbers stay inside agreed bounds."""
import random

from app.services.matching import score
from app.services.search.pipeline import order_pool
from app.validation.assessment import run
from app.validation.matching import _facts, _spec, make_dataset, rank


def test_assessment_validation_bounds():
    r = run(n=250, seed=3)
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

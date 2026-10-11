"""Side reports of the test validation: CAT against fixed forms, accuracy by distance to the cut, interval coverage."""
from __future__ import annotations

import random

from app.items.registry import BLUEPRINTS, families_for
from app.services.cat import CUTS
from app.validation import cat_baselines, cut_distance, interval_coverage
from app.validation.assessment import Session
from app.validation.sim_base import clean_run, digest


def _session(theta: float, target: str, passed: bool, theta_hat: float = 0.0, se: float = 0.5) -> Session:
    return Session("backend", target, theta, target if passed else None, passed, None, 10, [], [],
                   theta_hat, se, 0.8 if passed else 0.2)


def test_linear_form_is_fixed_and_spreads_levels():
    form = cat_baselines.linear_form("backend", 20)
    assert form == cat_baselines.linear_form("backend", 20)
    assert len(form) == 20
    levels = [lv for _, lv in form]
    assert set(levels) == {1, 2, 3, 4, 5}
    assert max(levels.count(lv) for lv in set(levels)) - min(levels.count(lv) for lv in set(levels)) <= 1
    topics = {f.topic for f, _ in form}
    assert topics <= set(BLUEPRINTS["backend"])
    assert all(f in families_for("backend") for f, _ in form)


def test_designs_have_the_asked_length_and_same_people():
    base = clean_run(12, 7)
    for design in ("cat", "linear", "random"):
        sessions = cat_baselines.design_sessions(base, design, 9)
        assert [s.theta for s in sessions] == [p[0] for p in base.people]
        assert all(s.n == 9 for s in sessions)


def test_items_to_se_counts_until_target():
    base = clean_run(6, 7)
    s = cat_baselines.design_sessions(base, "cat", 20)[0]
    k = cat_baselines.items_to_se(s, 0.5)
    assert k is None or 1 <= k <= 20
    assert cat_baselines.items_to_se(s, 0.0) is None


def test_paired_ci_zero_for_identical_designs():
    sessions = [_session(CUTS["middle"] + d, "middle", d > 0) for d in (-1.0, -0.2, 0.3, 1.2)]
    assert cat_baselines.paired_ci(sessions, sessions, clear_only=False) == (0.0, 0.0, 0.0)


def test_cut_distance_bins_and_monotone():
    cut = CUTS["middle"]
    sessions = [_session(cut + d, "middle", passed) for d, passed in
                [(0.05, False), (-0.05, False), (0.15, True), (0.7, True), (-0.7, False), (1.5, True)]]
    rows = cut_distance.bins(sessions)
    assert [r["n"] for r in rows] == [2, 1, 0, 0, 2, 1]
    assert rows[0]["accuracy"] == 0.5
    assert cut_distance.monotone(rows)
    rows[4]["accuracy"] = 0.4
    assert not cut_distance.monotone(rows)


def test_coverage_counts_inside_interval():
    rng = random.Random(3)
    sessions = []
    for _ in range(4000):
        theta = rng.gauss(0, 1)
        sessions.append(_session(theta, "middle", True, theta_hat=theta + rng.gauss(0, 0.5), se=0.5))
    c = interval_coverage.coverage(sessions)
    assert abs(c["cover"][0] - 0.683) < 0.03
    assert abs(c["cover"][2] - 0.95) < 0.02
    assert abs(c["z_sd"] - 1.0) < 0.05


def test_digest_is_stable():
    assert digest({"a": [1, 2.5]}) == digest({"a": [1, 2.5]})
    assert digest({"a": 1}) != digest({"a": 2})

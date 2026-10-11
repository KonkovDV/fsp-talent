"""AUC of neighbouring grades: the statistic itself and its stratified bootstrap interval."""
import math
import random

from app.validation.assessment import Session, adjacent_auc, auc


def test_auc_counts_pairs_and_halves_ties():
    assert auc([0.0, 1.0], [2.0, 3.0]) == 1.0
    assert auc([2.0, 3.0], [0.0, 1.0]) == 0.0
    assert auc([1.0], [1.0]) == 0.5
    # 3 of 4 pairs ordered, none tied
    assert auc([0.0, 2.0], [1.0, 3.0]) == 0.75
    assert math.isnan(auc([], [1.0]))


def test_auc_matches_brute_force_pair_count():
    rng = random.Random(1)
    lo = [round(rng.gauss(0, 1), 1) for _ in range(60)]
    hi = [round(rng.gauss(0.8, 1), 1) for _ in range(70)]
    brute = sum((h > x) + 0.5 * (h == x) for h in hi for x in lo) / (len(lo) * len(hi))
    assert abs(auc(lo, hi) - brute) < 1e-12


def _session(theta: float, theta_hat: float) -> Session:
    return Session(spec="backend", target="middle", theta=theta, earned=None, passed=False,
                   recommended=None, n=0, keys=[], theta_hat=theta_hat)


def test_adjacent_pairs_have_a_bootstrap_interval_around_the_point():
    rng = random.Random(2)
    # true θ: junior band [-1.5, -0.5), middle band [-0.5, 0.5)
    sessions = [_session(-1.0, rng.gauss(-1.0, 0.5)) for _ in range(100)]
    sessions += [_session(0.0, rng.gauss(0.0, 0.5)) for _ in range(100)]
    rows = adjacent_auc(sessions, draws=300)
    assert [(r.lower, r.upper) for r in rows] == [("junior", "middle")]
    row = rows[0]
    assert (row.n_lower, row.n_upper) == (100, 100)
    assert 0.8 < row.auc < 0.97
    assert row.ci[0] <= row.auc <= row.ci[1]
    assert row.ci[1] - row.ci[0] < 0.2


def test_small_groups_are_skipped_not_reported():
    sessions = [_session(-1.0, -1.0) for _ in range(5)] + [_session(0.0, 0.0) for _ in range(50)]
    assert adjacent_auc(sessions, draws=10) == []


def test_same_distribution_gives_half_and_the_interval_is_reproducible():
    rng = random.Random(3)
    sessions = [_session(-1.0, rng.gauss(0, 1)) for _ in range(1000)]
    sessions += [_session(0.0, rng.gauss(0, 1)) for _ in range(1000)]
    first = adjacent_auc(sessions, draws=200, seed=11)
    again = adjacent_auc(sessions, draws=200, seed=11)
    assert first == again
    assert abs(first[0].auc - 0.5) < 0.05


def test_report_lines_use_a_comma_and_add_the_mean():
    from types import SimpleNamespace

    from app.validation.assessment import AdjacentAuc, _auc_lines
    rows = [AdjacentAuc("junior", "middle", 30, 30, 0.9, (0.85, 0.95)),
            AdjacentAuc("middle", "senior", 30, 30, 0.8, (0.7, 0.9))]
    text = "\n".join(_auc_lines(SimpleNamespace(adjacent_auc=rows)))
    assert "| 0,900 | 0,850–0,950 |" in text
    assert "| среднее по парам | — | 0,850 | — |" in text
    assert "Экспресс-режима" in text

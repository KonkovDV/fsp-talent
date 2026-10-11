"""Retest kappa with a bootstrap interval (jury-gap A2: the unweighted κ alone undersells the test)."""
import random

from app.validation.assessment import _cohen_pass, _quadratic_kappa, kappa_bootstrap


def test_perfect_agreement_has_a_degenerate_interval():
    xs = ["junior", "middle", "senior", None] * 25
    assert _quadratic_kappa(xs, xs) == 1.0
    assert kappa_bootstrap(xs, xs, _quadratic_kappa) == (1.0, 1.0)


def test_interval_brackets_the_point_and_is_reproducible():
    rng = random.Random(3)
    grades = ["junior", "middle", "senior"]
    xs = [rng.choice(grades) for _ in range(300)]
    ys = [x if rng.random() < 0.7 else rng.choice(grades) for x in xs]
    point = _quadratic_kappa(xs, ys)
    lo, hi = kappa_bootstrap(xs, ys, _quadratic_kappa)
    assert lo < point < hi
    assert (lo, hi) == kappa_bootstrap(xs, ys, _quadratic_kappa)


def test_near_misses_count_less_than_far_misses():
    xs = ["junior", "middle", "senior"] * 50
    near = ["middle", "senior", "middle"] * 50
    far = ["senior", "junior", "junior"] * 50
    assert _quadratic_kappa(xs, near) > _quadratic_kappa(xs, far)


def test_pass_kappa_matches_the_formula():
    a = [True] * 60 + [False] * 40
    b = [True] * 50 + [False] * 10 + [True] * 10 + [False] * 30
    po, pe = 0.8, 0.6 * 0.6 + 0.4 * 0.4
    assert abs(_cohen_pass(a, b) - (po - pe) / (1 - pe)) < 1e-12

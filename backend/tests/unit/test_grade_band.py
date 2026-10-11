"""A grade decision near the cut is marked as borderline and reported separately."""
from app.validation.assessment import BAND_Z, CUTS, Session, _bootstrap_ci, borderline


def _session(theta_hat: float, se: float, target: str = "middle") -> Session:
    s = Session.__new__(Session)
    s.theta_hat, s.se, s.target = theta_hat, se, target
    return s


def test_band_is_one_standard_error_around_the_cut():
    cut = CUTS["middle"]
    assert BAND_Z == 1.0
    assert borderline(_session(cut + 0.29, 0.30))
    assert borderline(_session(cut - 0.29, 0.30))
    assert not borderline(_session(cut + 0.31, 0.30))
    assert not borderline(_session(cut - 0.61, 0.60))


def test_bootstrap_interval_contains_the_share_and_is_reproducible():
    flags = [True] * 90 + [False] * 10
    low, high = _bootstrap_ci(flags)
    assert low < 0.90 < high and 0.80 < low and high < 0.97
    assert _bootstrap_ci(flags) == (low, high)
    assert _bootstrap_ci([]) == (1.0, 1.0)

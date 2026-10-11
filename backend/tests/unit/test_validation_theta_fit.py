from types import SimpleNamespace

from app.validation.assessment import theta_fit


def test_theta_fit_is_exact_for_a_perfect_estimate_and_rmse_counts_the_shift():
    same = [SimpleNamespace(theta=t, theta_hat=t) for t in (-1.0, 0.0, 1.0, 2.0)]
    r, rmse = theta_fit(same)
    assert abs(r - 1.0) < 1e-9 and rmse == 0.0
    shifted = [SimpleNamespace(theta=t, theta_hat=t + 0.5) for t in (-1.0, 0.0, 1.0, 2.0)]
    r, rmse = theta_fit(shifted)
    assert abs(r - 1.0) < 1e-9 and abs(rmse - 0.5) < 1e-9

from app.validation.calibration_check import apply, ece, fit_isotonic


def test_isotonic_is_monotone_and_ece_drops_on_a_shifted_probability():
    ps = [i / 100 for i in range(100)]
    ys = [float(p > 0.3) for p in ps]
    edges, values = fit_isotonic(ps, ys)
    assert values == sorted(values)
    after = [apply(edges, values, p) for p in ps]
    assert ece(after, ys) < ece(ps, ys)

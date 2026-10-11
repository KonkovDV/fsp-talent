from app.validation.assessment import path_agreement


def test_same_and_adjacent_shares():
    same, near = path_agreement(["junior", "middle", None, "lead"], ["junior", "senior", "intern", "middle"])
    assert same == 0.25
    assert near == 0.75   # middle/senior and none/intern are one step apart; lead/middle are two


def test_empty_is_full_agreement():
    assert path_agreement([], []) == (1.0, 1.0)


def test_kappa_order_of_no_grade():
    from app.validation.assessment import _quadratic_kappa
    xs = [None, "intern", "junior", "middle", "senior", "lead"] * 5
    ys = ["intern", None, "junior", "middle", "senior", "lead"] * 5
    # One step apart when "no grade" sits below intern; the far end of the scale when it sits after lead.
    assert _quadratic_kappa(xs, ys, none_first=True) > _quadratic_kappa(xs, ys)
    assert _quadratic_kappa(xs, xs, none_first=True) == 1.0


def test_kappa_on_confirmed_pairs_ignores_no_grade():
    from app.validation.assessment import _quadratic_kappa, kappa_both_confirmed
    xs = [None, "intern", "junior", "middle", "senior", "lead"] * 5
    ys = ["intern", None, "junior", "middle", "senior", "lead"] * 5
    kappa, share = kappa_both_confirmed(xs, ys)
    assert share == 4 / 6
    assert kappa == 1.0
    assert kappa_both_confirmed([None], [None]) == (1.0, 0.0)
    assert _quadratic_kappa(xs, ys) < kappa

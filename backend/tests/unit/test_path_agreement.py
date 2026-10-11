from app.validation.assessment import path_agreement


def test_same_and_adjacent_shares():
    same, near = path_agreement(["junior", "middle", None, "lead"], ["junior", "senior", "intern", "middle"])
    assert same == 0.25
    assert near == 0.75   # middle/senior and none/intern are one step apart; lead/middle are two


def test_empty_is_full_agreement():
    assert path_agreement([], []) == (1.0, 1.0)

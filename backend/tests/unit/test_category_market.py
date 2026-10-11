"""The demo market seed picks a cell that can show quartiles without the demo need's pool."""
from seed.generate_seed import MARKET_K, pick_market_cell


def test_prefers_backend_middle_when_it_can_reach_target():
    assert pick_market_cell({("backend", "middle"): 2}, {("backend", "middle"): 4, ("qa", "junior"): 9}) == (
        "backend", "middle")


def test_falls_back_to_another_cell_when_backend_middle_sits_in_demo_need():
    # Stand on 11.10: backend·middle has 2 named sums and only 0 free profiles outside the demo need.
    named = {("backend", "middle"): 2, ("data", "junior"): 1}
    free = {("backend", "middle"): 0, ("data", "junior"): 5, ("embedded", "senior"): 20}
    assert pick_market_cell(named, free) == ("data", "junior")


def test_nothing_to_do_when_a_cell_already_shows_quartiles():
    assert pick_market_cell({("ml", "senior"): MARKET_K}, {("qa", "junior"): 9}) is None


def test_threshold_is_not_lowered():
    assert MARKET_K == 5

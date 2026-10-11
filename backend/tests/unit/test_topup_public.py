"""The public showcase top-up only adds, and the bank gives no total to subtract from."""
from app.services.search.pipeline import BANK_MIN, bank_cells
from seed.topup_public import CELLS, TARGET, missing_for


def test_target_respects_the_k_anonymity_threshold():
    assert BANK_MIN == 5 and TARGET >= BANK_MIN


def test_missing_only_tops_up_to_the_target_and_never_removes():
    counts = {("backend", "junior"): 9, ("backend", "middle"): 2, ("frontend", "senior"): TARGET}
    plan = {(s, g): n for s, g, n in missing_for(counts)}
    assert ("backend", "junior") not in plan and ("frontend", "senior") not in plan
    assert plan[("backend", "middle")] == TARGET - 2
    assert all(0 < n <= TARGET for n in plan.values())
    assert len(plan) == len(CELLS) - 2
    assert missing_for({cell: TARGET for cell in CELLS}) == []  # a second run adds nothing


def test_key_cells_cover_main_categories():
    for cell in [("backend", "middle"), ("frontend", "junior"), ("frontend", "middle"),
                 ("frontend", "senior"), ("ml", "junior"), ("ml", "middle"),
                 ("data", "junior"), ("data", "middle"), ("data", "senior")]:
        assert cell in CELLS


def test_a_hidden_cell_cannot_be_recovered_by_differencing():
    """The bank answer carries no per-role or overall total next to a hidden cell."""
    cells = bank_cells([("backend", "junior", 7, 3), ("backend", "middle", 3, 1), ("backend", "senior", 6, 2)])
    hidden = [c for c in cells if c["hidden"]]
    assert hidden == [{"role": "backend", "grade": "middle", "hidden": True, "candidates": None, "tested": None}]
    assert all(set(c) == {"role", "grade", "hidden", "candidates", "tested"} for c in cells)


def test_synthetic_profiles_do_not_get_the_printed_password():
    from app.core.security import verify_password
    from seed.generate_seed import DEMO_PASSWORD
    from seed.topup_public import unusable_password_hash
    assert not verify_password(DEMO_PASSWORD, unusable_password_hash())

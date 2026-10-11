"""Show, demote or hide candidates whose grade the test has not confirmed (F01)."""
import math

from app.validation.matching import apply_unconfirmed_policy, make_dataset, returned_share, unconfirmed_study


def _by_id():
    return {
        "a": {"observed": {"grade_source": "declared"}},
        "b": {"observed": {"grade_source": "assessed"}},
        "c": {"observed": {"grade_source": "declared"}},
        "d": {"observed": {"grade_source": "assessed"}},
    }


def test_policies_reorder_without_losing_confirmed_order():
    ranked = ["a", "b", "c", "d"]
    assert apply_unconfirmed_policy(ranked, _by_id(), "product") == ranked
    assert apply_unconfirmed_policy(ranked, _by_id(), "demote") == ["b", "d", "a", "c"]
    assert apply_unconfirmed_policy(ranked, _by_id(), "hide") == ["b", "d"]


def test_returned_share_counts_only_relevant_unconfirmed():
    labels = {"a": 3, "b": 3, "c": 0, "d": 2}
    assert returned_share(["a", "b"], labels, _by_id(), k=2) == 1.0
    assert returned_share(["b", "d"], labels, _by_id(), k=2) == 0.0
    assert math.isnan(returned_share(["a"], {"b": 3}, _by_id()))


def test_study_hides_nobody_relevant_in_product_and_delta_of_product_is_zero():
    rows = {r["policy"]: r for r in unconfirmed_study(make_dataset(120, 12, 5), rounds=50)}
    assert rows["product"]["d_ndcg"] == 0.0 and rows["product"]["d_p10"] == 0.0
    assert rows["hide"]["returned"] == 0.0
    assert rows["product"]["returned"] >= rows["demote"]["returned"]


def test_the_multiplier_grid_is_monotone_and_one_keeps_the_score():
    rows = {r["policy"]: r for r in unconfirmed_study(make_dataset(120, 12, 5), rounds=50)}
    grid = [rows[f"x{m}"]["returned"] for m in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert grid == sorted(grid)

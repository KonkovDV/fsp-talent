from app.services.exposure_fairness import impact_report, mark_top


def test_the_same_scores_in_two_regions_clear_four_fifths():
    scores = [0.2, 0.5, 0.9, 0.4, 0.8, 0.3, 0.7, 0.6, 0.55, 0.45]
    rows = []
    for tie, value in enumerate(scores):
        rows.append(("запад", value, tie))
        rows.append(("восток", value, tie))
    report = impact_report(mark_top(rows, 10))
    assert report["clears"] is True
    assert report["min_ratio"] == 1.0


def test_a_region_that_never_reaches_the_slice_is_below_the_floor():
    rows = [("запад", 0.9, i) for i in range(8)] + [("восток", 0.1, i) for i in range(8)]
    report = impact_report(mark_top(rows, 8))
    assert report["clears"] is False
    assert report["min_ratio"] == 0.0


def test_rates_half_and_thirty_five_hundredths_give_ratio_seven_tenths():
    from app.services.exposure_fairness import impact_report

    rows = [("a", i < 10) for i in range(20)] + [("b", i < 7) for i in range(20)] + [("c", True)] * 4
    report = impact_report(rows)
    assert report["min_ratio"] == 0.7
    assert report["clears"] is False
    small = [g for g in report["groups"] if g["region"] == "c"][0]
    assert small["n"] == 4 and "ratio" not in small


def test_skew_is_zero_when_top_mirrors_pool_and_negative_when_underrepresented():
    import math

    from app.services.exposure_fairness import skew_at_k

    pool = ["a", "b"] * 10
    assert skew_at_k(["a", "b"] * 5, pool, "a", 10) == 0.0
    assert math.isclose(skew_at_k(["a"] * 4 + ["b"] * 6, pool, "a", 10), math.log(0.8))
    assert skew_at_k(["b"] * 10, pool, "a", 10) is None


def test_live_fairness_report_is_deterministic_on_a_small_run():
    from app.validation.fairness import need_rows, report
    from app.validation.matching import make_dataset

    rows = need_rows(make_dataset(120, 6, 7))
    first, summary = report(rows, 20)
    second, _ = report(need_rows(make_dataset(120, 6, 7)), 20)
    assert first == second
    assert "Регион" in first and "Skew@10" in first
    assert 0.0 <= summary["region_min_sel"] <= 1.0

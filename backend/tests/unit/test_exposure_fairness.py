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

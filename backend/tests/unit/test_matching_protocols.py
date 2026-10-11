from app.validation import protocols as P


def test_labels_in_range_and_metrics():
    from app.validation.matching import make_dataset
    data = make_dataset(120, 6, 2026)
    for need in data["needs"]:
        for c in data["candidates"]:
            assert P.label_a(need, c) in (0, 1, 2, 3)
            assert P.label_b(need, c) in (0, 1, 2, 3)
    labels = {"x": 0, "y": 2, "z": 3}
    assert P.mrr(["x", "y", "z"], labels) == 0.5
    assert P.precision10(["y", "z"], labels) == 0.2


def test_other_role_is_zero():
    need = {"role": "backend", "grade": "middle", "skills": ["SQL"], "work_format": None}
    cand = {"truth": {"role": "zzz", "grade": "middle", "skills": ["SQL"], "theta": 0.0}, "observed": {}}
    assert P.label_a(need, cand) == 0 and P.label_b(need, cand) == 0

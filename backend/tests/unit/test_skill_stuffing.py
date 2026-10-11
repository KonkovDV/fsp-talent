"""Skill stuffing: a share of candidates declare every skill of their role (T5)."""
from app.validation.matching import _pool, make_dataset, stuff_skills, stuffing_study


def test_stuffing_adds_every_role_skill_and_keeps_truth_and_labels():
    data = make_dataset(100, 5, 3)
    stuffed_data, stuffed = stuff_skills(data, share=0.3, seed=1)
    assert 10 < len(stuffed) < 50
    by_id = {c["id"]: c for c in stuffed_data["candidates"]}
    for cid in stuffed:
        c = by_id[cid]
        assert set(_pool(c["observed"]["role"])) <= set(c["observed"]["skills"])
    assert stuffed_data["labels"] == data["labels"]
    original = {c["id"]: c for c in data["candidates"]}
    assert all(by_id[i]["truth"] == original[i]["truth"] for i in by_id)
    # the source dataset is not modified
    assert stuff_skills(data, share=0.3, seed=1)[1] == stuffed


def test_study_reports_both_methods_with_a_control():
    rows = {r["method"]: r for r in stuffing_study(make_dataset(150, 8, 4), share=0.2)}
    assert set(rows) == {"full", "keyword", "full, всё подтверждено"}
    # Trust weights are what keeps stuffing down: taking every claim as confirmed lets more stuffers in.
    assert rows["full, всё подтверждено"]["top"] >= rows["full"]["top"]
    for r in rows.values():
        assert 0.0 <= r["before"] <= 1.0 and 0.0 <= r["top"] <= 1.0
        assert r["top_ci"][0] <= r["top"] <= r["top_ci"][1]

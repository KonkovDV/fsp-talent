"""The comparable-data scenario changes only what the ranker sees, never truth, labels or needs."""
from app.validation.matching import make_dataset


def test_clean_keeps_truth_labels_and_needs():
    a = make_dataset(120, 12, 2026)
    b = make_dataset(120, 12, 2026, clean=True)
    assert a["labels"] == b["labels"] and a["needs"] == b["needs"]
    assert [c["truth"] for c in a["candidates"]] == [c["truth"] for c in b["candidates"]]
    for c in b["candidates"]:
        o, t = c["observed"], c["truth"]
        assert o["grade"] == t["grade"] and o["grade_source"] == "assessed"
        assert set(o["skills"]) <= set(t["skills"])

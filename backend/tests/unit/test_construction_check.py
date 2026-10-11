from app.validation import construction_check as cc


def test_collision_rates_cover_concept_families():
    import random
    rates = cc.collision_rates(random.Random(1), pairs=3)
    kinds = {cc.FAMILIES[k].kind for k in rates}
    assert "concept" in kinds and "code" in kinds
    assert all(0.0 <= v <= 1.0 for v in rates.values())


def test_transfer_lift_is_measured_against_same_people():
    t = cc.transfer_lift(12, 3)
    assert t["people"] == 12
    assert 0.0 <= t["honest"] <= 1.0 and 0.0 <= t["attack"] <= 1.0


def test_model_rows_three_answer_models():
    rows = cc.model_rows(40, 5)
    assert len(rows) == 3
    for _, r in rows:
        assert 0.0 <= r["overclaim_rejected"] <= 1.0

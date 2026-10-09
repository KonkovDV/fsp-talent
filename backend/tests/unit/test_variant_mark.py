"""A copied key from another variant is a mark. The grade function is not called."""
from app.services.variant_mark import collision_rate, foreign_variant


def test_collision_rate_skips_a_family_that_repeats_keys():
    assert collision_rate(["7"] * 60) == 1
    assert collision_rate([str(i) for i in range(60)]) == 0


def test_own_right_answer_is_not_a_foreign_variant():
    assert foreign_variant("py_eval", "backend", 1, "12", "12") is False


def test_a_key_from_another_draw_is_marked_only_when_collisions_are_rare():
    from app.services.variant_mark import _sample_keys
    keys = _sample_keys("py_eval", "backend", 1)
    if keys is None:
        assert foreign_variant("py_eval", "backend", 1, "1", "2") is False
    else:
        stolen = next(key for key in keys if key != "999999")
        assert foreign_variant("py_eval", "backend", 1, "999999", stolen) is True

from app.validation.instance_exposure import fingerprint, low_variety, max_share, mean_overlap


def test_same_instance_has_one_fingerprint_and_other_numbers_change_it():
    a = ("py_eval", 3, "x = 2 + 3", "print(x)")
    assert fingerprint(a) == fingerprint(tuple(a))
    assert fingerprint(a) != fingerprint(("py_eval", 3, "x = 2 + 4", "print(x)"))
    assert len(fingerprint(a)) == 64


def test_exposure_one_of_four_sessions_is_a_quarter():
    share, item = max_share([{"a"}, {"b"}, {"c"}, {"d", "e"}])
    assert share == 0.25
    assert item in {"a", "b", "c", "d", "e"}


def test_overlap_and_low_variety_flag():
    assert mean_overlap([{"a"}, {"a"}]) == 1.0
    assert mean_overlap([{"a"}, {"b"}]) == 0.0

    class S:
        def __init__(self, spec):
            self.spec = spec

    rows = [(S("qa"), {"x"}), (S("qa"), {"x"})] + [(S("qa"), {f"y{i}"}) for i in range(8)]
    assert low_variety(rows, {"x": "fam_x"}) == [("fam_x", 0.2)]

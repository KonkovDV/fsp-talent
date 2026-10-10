from app.services.matching import near_pairs


def test_grade_matches_one_step_by_default():
    from app.services.matching import grade_matches
    assert grade_matches("lead", "senior") is True
    assert grade_matches("junior", "senior") is False
    assert grade_matches("junior", "senior", "exact") is False
    assert grade_matches("junior", "senior", "any") is True
    assert grade_matches("middle", None) is True


def test_a_middle_backend_keeps_one_grade_step_and_neighbour_roles():
    pairs = near_pairs("backend", "middle")
    assert pairs[0] == ("backend", "middle")
    assert ("backend", "junior") in pairs
    assert ("backend", "senior") in pairs
    assert ("backend", "lead") not in pairs
    assert ("fullstack", "middle") in pairs
    assert ("frontend", "middle") not in pairs
    assert ("fullstack", "junior") not in pairs


def test_exact_span_is_only_the_named_pair():
    from app.services.matching import category_pairs
    assert category_pairs("backend", "middle", "exact") == [("backend", "middle")]
    assert category_pairs("backend", "middle", "near") == near_pairs("backend", "middle")
    assert category_pairs("backend", "middle", "wide") is None
    assert category_pairs("backend", "middle", "any") is None
    plus = category_pairs("backend", "middle", "plus_minus")
    assert plus == [("backend", "middle"), ("backend", "junior"), ("backend", "senior")]


def test_the_ends_of_the_ladder_have_only_one_grade_step():
    assert ("backend", "junior") in near_pairs("backend", "intern")
    assert ("backend", "middle") not in near_pairs("backend", "intern")
    assert ("backend", "senior") in near_pairs("backend", "lead")
    assert ("backend", "middle") not in near_pairs("backend", "lead")

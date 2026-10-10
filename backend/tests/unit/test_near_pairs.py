from app.services.matching import near_pairs


def test_a_middle_backend_keeps_one_grade_step_and_neighbour_roles():
    pairs = near_pairs("backend", "middle")
    assert pairs[0] == ("backend", "middle")
    assert ("backend", "junior") in pairs
    assert ("backend", "senior") in pairs
    assert ("backend", "lead") not in pairs
    assert ("fullstack", "middle") in pairs
    assert ("frontend", "middle") not in pairs
    assert ("fullstack", "junior") not in pairs


def test_the_ends_of_the_ladder_have_only_one_grade_step():
    assert ("backend", "junior") in near_pairs("backend", "intern")
    assert ("backend", "middle") not in near_pairs("backend", "intern")
    assert ("backend", "senior") in near_pairs("backend", "lead")
    assert ("backend", "middle") not in near_pairs("backend", "lead")

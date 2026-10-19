from app.services.design_probe import contrast_ratio, judge, puzzle


def test_gray_on_white_is_below_the_contrast_floor():
    assert contrast_ratio((170, 170, 170), (255, 255, 255)) < 4.5
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) >= 4.5


def test_the_probe_names_a_computed_defect_and_does_not_move_the_grade():
    shown = puzzle("layout-seed")
    assert shown["grade_unchanged"] is True
    assert "answer" not in shown
    right = next(choice for choice in shown["choices"] if judge("layout-seed", choice)["matched"])
    assert judge("layout-seed", right) == {"matched": True, "grade_unchanged": True}
    wrong = next(choice for choice in shown["choices"] if choice != right)
    assert judge("layout-seed", wrong)["matched"] is False

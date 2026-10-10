from app.services.matching import standing_line


def test_the_line_says_which_side_of_the_average():
    assert standing_line(70, "Backend × middle").startswith("Выше среднего")
    assert standing_line(20, "Backend × middle").startswith("Ниже среднего")
    assert standing_line(50, "Backend × middle").startswith("На среднем уровне")
    assert "лучше 70 %" in standing_line(70, "Backend × middle")

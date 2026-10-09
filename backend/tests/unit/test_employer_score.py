"""The company figure is a labelled demo score and stays inside 0..10."""
from app.services.employer_score import company_score


def test_a_known_name_is_stable_and_labelled_as_demo():
    first = company_score("Сибирский код")
    assert first == company_score("Сибирский код")
    assert first["demo"] is True and 0 <= first["score"] <= 10
    assert first["label"] in ("низкий", "средний", "высокий")
    assert "tier" not in first


def test_an_unknown_name_does_not_leave_the_scale():
    row = company_score("Несуществующая контора 42")
    assert 0 <= row["score"] <= 10 and row["demo"] is True

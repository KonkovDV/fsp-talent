"""City and work format drop an explicit mismatch. They are not a match-score input."""
from app.services.cities import city_name, place_keeps
from app.services.matching import score


def test_the_filter_keeps_an_unnamed_field_and_drops_a_mismatch():
    assert city_name("москва") == "Москва"
    assert city_name("Мск") is None
    assert place_keeps(None, [], "Москва", "remote") is True
    assert place_keeps("Казань", ["remote"], "Москва", None) is False
    assert place_keeps("Москва", ["office"], "Москва", "remote") is False
    assert place_keeps("Москва", ["remote", "hybrid"], None, "remote") is True


def test_the_match_score_does_not_take_a_city():
    assert "city" not in score.__code__.co_varnames

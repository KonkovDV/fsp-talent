"""City and work format stay in the list. The match score lowers a mismatch."""
from app.services.cities import city_name, place_keeps
from app.services.matching import CandidateFacts, NeedSpec, score


def test_a_mismatch_stays_in_the_list_and_scores_lower():
    assert city_name("москва") == "Москва"
    assert city_name("Мск") is None
    assert place_keeps("Казань", ["office"], "Москва", "remote") is True
    need = NeedSpec(role="backend", grade="middle", skills=("Python",), city="Москва", work_format="remote")
    here = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                          skills={"Python": "test_confirmed"}, city="Москва", work_formats=("remote",))
    away = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                          skills={"Python": "test_confirmed"}, city="Казань", work_formats=("office",))
    assert score(need, here).score > score(need, away).score

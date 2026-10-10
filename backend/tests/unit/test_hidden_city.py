from app.services.matching import CandidateFacts, NeedSpec, score


def _lines(result) -> str:
    return " ".join(result.plus + result.minus + result.info)


def test_a_hidden_city_scores_the_same_whichever_city_is_filtered():
    person = CandidateFacts(role="backend", grade="middle", grade_source="assessed", city=None)
    moscow = score(NeedSpec(city="Москва"), person)
    kazan = score(NeedSpec(city="Казань"), person)
    assert moscow.score == kazan.score
    assert "Москва" not in _lines(moscow) and "Казань" not in _lines(kazan)
    shown = score(NeedSpec(city="Москва"), CandidateFacts(
        role="backend", grade="middle", grade_source="assessed", city="Москва"))
    assert "Москва" in _lines(shown)

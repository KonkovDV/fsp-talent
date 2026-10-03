from app.services.skills import extract_skills, is_grounded, normalize_skill


def test_aliases_and_cyrillic_lookalikes():
    assert normalize_skill("питон") == "Python"
    assert normalize_skill("постгрес") == "PostgreSQL"
    assert normalize_skill("С++") == "C++"
    assert normalize_skill("pg") is None
    assert normalize_skill("C") == "C"
    assert all(item.skill != "C" for item in extract_skills("option c, not a language"))


def test_extraction_keeps_original_evidence():
    found = {s.skill: s.evidence for s in extract_skills("Пишу на Python и С++, знаю язык си")}
    assert found["Python"] == "Python"
    assert found["C++"] == "С++"
    assert found["C"] == "язык си"


def test_grounding_requires_a_real_substring():
    text = "Опыт: FastAPI и PostgreSQL"
    assert is_grounded("FastAPI", text)
    assert not is_grounded("Django", text)
    assert not is_grounded("  ", text)

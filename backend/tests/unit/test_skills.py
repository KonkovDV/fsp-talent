from datetime import UTC, datetime

from app.services.skills import SkillDraft, extract_skills, is_grounded, normalize_skill, plan_skill_replacement


def test_aliases_and_cyrillic_lookalikes():
    assert normalize_skill("питон") == "Python"
    assert normalize_skill("постгрес") == "PostgreSQL"
    assert normalize_skill("С++") == "C++"
    assert normalize_skill("pg") is None
    assert normalize_skill("C") == "C"
    assert normalize_skill("голанг") == "Go"
    assert normalize_skill("джаваскрипт") == "JavaScript"
    assert normalize_skill("кубернетес") == "Kubernetes"
    assert normalize_skill("фастапи") == "FastAPI"
    assert all(item.skill != "C" for item in extract_skills("option c, not a language"))
    assert all(item.skill != "Rust" for item in extract_skills("проект растёт второй год"))


def test_extraction_keeps_original_evidence():
    found = {s.skill: s.evidence for s in extract_skills("Пишу на Python и С++, знаю язык си")}
    assert found["Python"] == "Python"
    assert found["C++"] == "С++"
    assert found["C"] == "язык си"


def test_saving_the_profile_keeps_skill_evidence():
    earlier = datetime(2026, 5, 1, tzinfo=UTC)
    now = datetime(2026, 10, 6, tzinfo=UTC)
    existing = [
        SkillDraft("Python", "Python", "Тест 01.05.2026: 90% верных ответов", "test_confirmed", True, earlier, earlier),
        SkillDraft("PostgreSQL", "PostgreSQL", "PostgreSQL", "resume_confirmed", True, earlier, earlier),
        SkillDraft("Docker", "Docker", None, "self_reported", True, earlier, None),
    ]
    saved = plan_skill_replacement(existing, [
        ("Python", "питон", None),
        ("PostgreSQL", "PostgreSQL", "PostgreSQL"),
        ("Docker", "Docker", "Docker"),
        ("", "не навык", None),
        ("Redis", "Redis", None),
    ], now)
    by_name = {row.name: row for row in saved}
    assert list(by_name) == ["Python", "PostgreSQL", "Docker", "Redis"]
    assert by_name["Python"].trust_level == "test_confirmed"
    assert by_name["Python"].confirmed_at == earlier
    assert by_name["Python"].source_quote.startswith("Тест")
    assert by_name["PostgreSQL"].confirmed_at == earlier
    assert by_name["Docker"].trust_level == "resume_confirmed" and by_name["Docker"].confirmed_at == now
    assert by_name["Redis"].trust_level == "self_reported" and by_name["Redis"].confirmed_at is None
    assert by_name["Redis"].created_at == now


def test_grounding_requires_a_real_substring():
    text = "Опыт: FastAPI и PostgreSQL"
    assert is_grounded("FastAPI", text)
    assert not is_grounded("Django", text)
    assert not is_grounded("  ", text)

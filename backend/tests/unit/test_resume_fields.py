"""Resume fields come only from a verbatim quote: a job title is not a name, a study span is not tenure."""
import asyncio

from app.services.ai import assistant
from app.services.ai.assistant import extract_resume_fields, for_model, parse_resume
from app.services.skills import is_grounded

TEXT = """
Иванов Пётр Сергеевич
Backend-разработчик, middle
Москва
почта: petr.ivanov@example.com
тел. +7 (900) 111-22-33
telegram: @petr_demo
Стаж 4 года коммерческой разработки.
Пишу сервисы на Python и FastAPI.
Люблю командную работу и менторство.
"""


def _quotes(fields: dict) -> list[str]:
    quotes = [fields[key]["quote"] for key in
              ("full_name", "email", "phone", "telegram", "experience_years", "grade", "role") if fields[key]]
    quotes += [item["quote"] for item in fields["soft_skills"]]
    return quotes


def test_resume_fields_are_quoted_from_the_text():
    fields = extract_resume_fields(TEXT)
    assert fields["full_name"]["value"] == "Иванов Пётр Сергеевич"
    assert fields["email"]["value"] == "petr.ivanov@example.com"
    assert fields["phone"]["value"] == "+79001112233"
    assert fields["telegram"]["value"] == "@petr_demo"
    assert fields["experience_years"]["value"] == 4
    assert fields["grade"]["value"] == "middle"
    assert fields["role"]["value"] == "backend"
    assert {item["name"] for item in fields["soft_skills"]} == {"Командная работа", "Наставничество"}
    assert all(is_grounded(quote, TEXT) for quote in _quotes(fields))


def test_eight_starts_a_phone_and_a_title_is_not_a_name():
    fields = extract_resume_fields("Python Developer\n8 900 111 22 33\n3 года обучения в университете")
    assert fields["full_name"] is None
    assert fields["phone"]["value"] == "+79001112233"
    assert fields["experience_years"] is None
    assert fields["grade"] is None and fields["role"] is None


def test_the_model_does_not_see_the_name_or_contacts():
    cleaned = for_model(TEXT)
    assert "Иванов" not in cleaned and "example.com" not in cleaned
    assert "@petr_demo" not in cleaned and "900" not in cleaned
    assert "Python" in cleaned and "FastAPI" in cleaned


def test_parse_resume_sends_the_model_the_redacted_text(monkeypatch):
    seen = {}

    async def fake(text):
        seen["text"] = text
        return [{"skill": "PostgreSQL", "quote": "этой цитаты нет в тексте"}]

    monkeypatch.setattr(assistant, "_llm_skills", fake)
    monkeypatch.setattr(assistant.settings, "AI_ENABLED", True)
    monkeypatch.setattr(assistant.settings, "GIGACHAT_CREDENTIALS", "demo")
    result = asyncio.run(parse_resume(TEXT))
    assert "example.com" not in seen["text"] and "Иванов" not in seen["text"]
    assert result["llm_rejected"] == 1
    assert result["full_name"]["value"] == "Иванов Пётр Сергеевич"


def test_parse_resume_keeps_skills_next_to_the_fields():
    result = asyncio.run(parse_resume(TEXT))
    assert sorted(item["name"] for item in result["skills"]) == ["FastAPI", "Python"]
    assert result["experience_years"]["value"] == 4
    assert all(is_grounded(item["source_quote"], TEXT) for item in result["skills"])

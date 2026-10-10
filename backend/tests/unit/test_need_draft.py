from app.services.need_draft import draft_need

TEXT = """Backend-разработчик, мидл
Москва, удалённо, финтех.
Python, PostgreSQL, от 180 000 до 260 000.
Будет плюсом: Docker.
"""


def test_a_pasted_vacancy_fills_the_need_and_keeps_the_bonus_apart():
    draft = draft_need(TEXT)
    assert draft["role"] == "backend"
    assert draft["grade"] == "middle"
    assert "Python" in draft["skills"] and "PostgreSQL" in draft["skills"]
    assert draft["nice_to_have"] == ["Docker"]
    assert draft["salary_from"] == 180_000 and draft["salary_to"] == 260_000
    assert draft["work_format"] == "remote" and draft["city"] == "Москва"
    assert draft["industry"] == "fintech"
    assert draft["notes"] == []


def test_an_empty_text_lists_what_to_fill():
    notes = draft_need("Ищем человека в команду")["notes"]
    assert any("навык" in line for line in notes)
    assert any("Вилка" in line for line in notes)

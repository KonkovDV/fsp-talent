import json

from app.services.telegram_digest import achievement_digest, clean_fsp_id, vacancy_digest


def test_an_fsp_id_is_the_short_public_form():
    assert clean_fsp_id(" fsp001 ") == "FSP001"
    assert clean_fsp_id("anna@demo.talent") is None
    assert clean_fsp_id("FSP") is None


def test_achievements_have_no_name_and_do_not_set_a_grade():
    body = achievement_digest("FSP001", [{
        "discipline": "Алгоритмика", "year": 2025, "bucket": "топ-10%", "status": "Чемпионат России",
        "display_name": "Анна", "place": 3, "email": "a@b.ru",
    }])
    raw = json.dumps(body, ensure_ascii=False)
    assert "Анна" not in raw and "a@b.ru" not in raw and "place" not in raw
    assert body["items"][0] == {
        "discipline": "Алгоритмика", "year": 2025, "bucket": "топ-10%", "status": "Чемпионат России",
    }
    assert "не ставится" in body["text"]


def test_an_unknown_id_and_an_empty_protocol_look_the_same():
    text = achievement_digest("FSP999", [])["text"]
    assert "Протоколов нет." in text
    assert "не ставится" in text


def test_the_vacancy_list_names_the_company_and_not_a_candidate():
    body = vacancy_digest([{
        "company": "Сибирский код", "title": "Backend", "role": "Backend-разработка",
        "grade": "мидл", "work_format": "удалённо", "salary_from": 180000, "salary_to": 260000,
        "candidate": "Иван",
    }])
    raw = json.dumps(body, ensure_ascii=False)
    assert "Сибирский код" in raw and "Иван" not in raw
    assert "Имён кандидатов здесь нет." in body["text"]

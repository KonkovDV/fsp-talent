import pytest

from app.services.cities import find_city
from app.services.need_draft import draft_need, salary_range

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


# --- T1: salary range, city case forms, stack-named titles ---

@pytest.mark.parametrize(("text", "expected"), [
    ("от 150 до 250 тыс", (150_000, 250_000)),
    ("Вилка 150–250k gross", (150_000, 250_000)),
    ("120–160 тыс. руб. на руки", (120_000, 160_000)),
    ("180k–240k", (180_000, 240_000)),
    ("от 200 тыс. до 260 тыс. рублей", (200_000, 260_000)),
    ("200 000 ₽ – 280 000 ₽ net", (200_000, 280_000)),
    ("90 000 - 130 000 рублей до вычета НДФЛ", (90_000, 130_000)),
    ("1,5–2 млн руб.", (1_500_000, 2_000_000)),
])
def test_salary_range_keeps_both_bounds(text, expected):
    assert salary_range(text) == expected


@pytest.mark.parametrize("text", [
    "Опыт от 2 до 4 лет, команда 10–15 человек",
    "Работаем с 9:00 до 18:00, премия до 20%",
    "Телефон +7 (912) 345-67-89",
    "до 300 000 ₽",
])
def test_non_salary_numbers_and_single_bounds_are_not_a_range(text):
    assert salary_range(text) is None


def test_a_single_bound_fills_both_fields():
    draft = draft_need("Python-разработчик\nДо 300 000 ₽ на руки.")
    assert (draft["salary_from"], draft["salary_to"]) == (300_000, 300_000)


def test_experience_years_do_not_hide_the_salary_range():
    draft = draft_need("Java-разработчик\nОпыт от 3 до 5 лет. Зарплата 250–320 тыс.")
    assert (draft["salary_from"], draft["salary_to"]) == (250_000, 320_000)


@pytest.mark.parametrize(("text", "city"), [
    ("Офис в Москве", "Москва"),
    ("Переезд из Новосибирска", "Новосибирск"),
    ("Гибрид, СПб", "Санкт-Петербург"),
    ("Работаем в Питере", "Санкт-Петербург"),
    ("в Казани", "Казань"),
    ("офис в Перми", "Пермь"),
    ("в Уфе", "Уфа"),
    ("в Нижнем Новгороде", "Нижний Новгород"),
    ("из Ростова-на-Дону", "Ростов-на-Дону"),
    ("начинающий разработчик в Екб", "Екатеринбург"),
])
def test_city_is_found_in_any_case_form_or_short_name(text, city):
    assert find_city(text) == city


def test_city_needs_a_whole_word_and_the_first_mention_wins():
    assert find_city("уфолог, московский проект") is None
    assert find_city("Офис в Новосибирске, филиал в Москве") == "Новосибирск"


@pytest.mark.parametrize(("title", "role"), [
    ("Go-разработчик, senior", "backend"),
    ("Golang-разработчик (Middle)", "backend"),
    ("Senior Go developer", "backend"),
    ("Junior Java-разработчик", "backend"),
    ("Разработчик Python", "backend"),
    ("C#-разработчик", "backend"),
    ("Vue-разработчик", "frontend"),
    ("Flutter-разработчик", "mobile"),
])
def test_a_stack_in_the_title_names_the_specialization(title, role):
    assert draft_need(f"{title}\nОфис.")["role"] == role


def test_ambiguous_languages_and_plain_words_name_no_specialization():
    assert draft_need("Rust-разработчик\nОфис.")["role"] is None
    assert draft_need("Разработчик C++\nОфис.")["role"] is None
    assert draft_need("Менеджер проектов\nЛюбим Go-карты по пятницам.")["role"] is None


def test_the_title_role_beats_a_role_word_in_the_body():
    draft = draft_need("Стажёр-тестировщик\nНаучим тестированию мобильных приложений.")
    assert draft["role"] == "qa"


def test_robotics_developer_is_embedded_and_internship_sets_intern_grade():
    assert draft_need("Робототехник-программист\nROS, C++.")["role"] == "embedded"
    draft = draft_need("Python-разработчик (стажировка)\nОплачиваемая стажировка.")
    assert draft["grade"] == "intern" and draft["work_goal"] == "internship"

from app.services.career_gap import career_gap, career_hint


def test_confirming_the_only_gap_counts_the_vacancies_it_would_close():
    hint = career_gap({"Python"}, [{"Python", "PostgreSQL"}, {"Python", "PostgreSQL"}, {"Kafka"}])
    assert hint == {"skill": "PostgreSQL", "gained": 2, "vacancies": 3}


def test_two_gaps_or_a_covered_vacancy_do_not_invent_a_hint():
    assert career_gap({"Python"}, [{"Python"}, {"Go", "Kafka"}]) is None


def test_a_narrower_confirmed_tool_is_not_a_gap_for_the_general_skill():
    assert career_gap({"FastAPI"}, [{"Python"}]) is None
    hint = career_gap({"FastAPI"}, [{"Python", "PostgreSQL"}, {"Python", "PostgreSQL"}])
    assert hint == {"skill": "PostgreSQL", "gained": 2, "vacancies": 2}


def test_the_hint_stays_closed_until_three_companies_open_the_card():
    vacancies = [{"Python", "PostgreSQL"}, {"Python", "PostgreSQL"}]
    closed = career_hint({"Python"}, vacancies, 2)
    assert closed["open"] is False and closed["skill"] is None and closed["need_companies"] == 3
    opened = career_hint({"Python"}, vacancies, 3)
    assert opened == {"skill": "PostgreSQL", "gained": 2, "vacancies": 2, "open": True}

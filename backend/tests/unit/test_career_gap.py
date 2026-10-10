from app.services.career_gap import career_gap


def test_confirming_the_only_gap_counts_the_vacancies_it_would_close():
    hint = career_gap({"Python"}, [{"Python", "PostgreSQL"}, {"Python", "PostgreSQL"}, {"Kafka"}])
    assert hint == {"skill": "PostgreSQL", "gained": 2, "vacancies": 3}


def test_two_gaps_or_a_covered_vacancy_do_not_invent_a_hint():
    assert career_gap({"Python"}, [{"Python"}, {"Go", "Kafka"}]) is None

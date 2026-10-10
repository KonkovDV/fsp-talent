from app.services.certificate_evidence import certificate_skills


def test_a_certificate_keeps_a_quoted_skill_and_a_letter_is_not_a_grade():
    text = "Свидетельство КИТ i.moscow. Подтверждены навыки: Python и PostgreSQL."
    rows = certificate_skills(text)
    assert rows is not None
    assert ("Python", "Python") in rows or any(name == "Python" for name, _ in rows)
    assert all("grade" not in name for name, _ in rows)


def test_a_file_without_the_marker_is_not_a_certificate():
    assert certificate_skills("Резюме. Знаю Python.") is None

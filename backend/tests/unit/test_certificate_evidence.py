from app.services.certificate_evidence import certificate_skills


def test_a_certificate_keeps_a_quoted_skill_and_a_letter_is_not_a_grade():
    text = "Свидетельство КИТ i.moscow. Подтверждены навыки: Python и PostgreSQL."
    rows = certificate_skills(text)
    assert rows is not None
    assert ("Python", "Python") in rows or any(name == "Python" for name, _ in rows)
    assert all("grade" not in name for name, _ in rows)


def test_a_file_without_the_marker_is_not_a_certificate():
    assert certificate_skills("Резюме. Знаю Python.") is None


def test_aud02_marker_is_a_whole_word_and_only_pdf_counts():
    from app.services.certificate_evidence import certificate_skills, is_pdf
    assert certificate_skills("Никита знает китайский, Python и Docker") is None
    assert certificate_skills("Сертификат КИТ: Python") is not None
    assert is_pdf(b"%PDF-1.7\n...")
    assert not is_pdf("Я освоил".encode())


def test_aud02_certificate_skills_are_never_confirmed():
    import inspect

    from app.api.v1 import candidates
    source = inspect.getsource(candidates.import_certificate)
    assert '"resume_confirmed"' not in source and '"test_confirmed"' not in source.split("continue")[-1]
    assert 'row.trust_level = "self_reported"' in source

"""G1: field-level validation of resume and vacancy parsing is deterministic and measures the real parsers."""
from __future__ import annotations

import random

import pytest

from app.services.ai.assistant import extract_resume_fields
from app.services.pdf_profile import _font, extract_pdf_text
from app.validation import nlp

needs_font = pytest.mark.skipif(_font() is None, reason="no Cyrillic font")


def test_prf_matches_definition():
    assert nlp.prf({"a", "b"}, {"a"}) == (0.5, 1.0, 0.667)
    assert nlp.prf(set(), set()) == (1.0, 1.0, 1.0)
    assert nlp.prf({"x"}, {"y"}) == (0.0, 0.0, 0.0)


def test_mean_prf_averages_columns_and_handles_no_documents():
    assert nlp.mean_prf([(1.0, 0.5, 0.6), (0.5, 0.5, 0.5)]) == {"p": 0.75, "r": 0.5, "f1": 0.55}
    assert nlp.mean_prf([]) == {"p": None, "r": None, "f1": None}


def test_persona_is_consistent():
    for i in range(50):
        p = nlp.make_persona(random.Random(i), i)
        low, high = nlp.YEARS[p.grade]
        assert low <= p.experience_years <= high
        assert p.skills <= set(nlp.TRACKS[p.role][1])
        assert p.phone.startswith("+7") and len(p.phone) == 12
        assert sum(ch.isdigit() for ch in p.phone_text) == 11


def test_plural_years():
    assert [nlp._plural_years(n) for n in (1, 2, 5, 11, 12, 21, 22, 25)] == [
        "год", "года", "лет", "лет", "лет", "год", "года", "лет"]


@needs_font
@pytest.mark.parametrize("layout", nlp.LAYOUTS)
def test_known_name_and_email_are_read_back_from_every_layout(layout):
    p = nlp.make_persona(random.Random(7), 0)
    text = extract_pdf_text(nlp.render_pdf(nlp.RENDERERS[layout](p, random.Random(7))))
    fields = extract_resume_fields(text)
    assert fields["full_name"]["value"] == p.full_name
    assert fields["email"]["value"] == p.email


@needs_font
def test_empty_pdf_gives_no_fields_and_no_error():
    text = extract_pdf_text(nlp.render_pdf([("t", "")]))
    fields = extract_resume_fields(text)
    assert all(fields[k] is None for k in ("full_name", "email", "phone", "telegram", "experience_years"))


@needs_font
def test_two_runs_give_the_same_report():
    assert nlp.resume_eval(4, 11) == nlp.resume_eval(4, 11)


def test_vacancy_gold_set_is_scored():
    report = nlp.vacancy_eval()
    assert report["n"] == 24
    assert set(report) >= {"role", "grade", "salary", "work_format", "city", "skills", "misses"}
    assert set(report["skills"]) == {"required", "optional", "union"}
    assert 0.0 <= report["skills"]["required"]["f1"] <= 1.0

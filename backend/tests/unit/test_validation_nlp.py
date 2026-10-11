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


@needs_font
def test_known_name_is_extracted_from_rendered_pdf():
    p = nlp.person(random.Random(7), 0)
    text = extract_pdf_text(nlp.render_pdf(nlp.lines_hh(p, random.Random(7)), True))
    assert extract_resume_fields(text)["full_name"]["value"] == p["full_name"]


@needs_font
def test_empty_pdf_gives_no_fields_and_no_error():
    text = extract_pdf_text(nlp.render_pdf([("", "")], False))
    fields = extract_resume_fields(text)
    assert all(fields[k] is None for k in ("full_name", "email", "phone", "telegram", "experience_years"))


@needs_font
def test_two_runs_give_the_same_report():
    assert nlp.resume_eval(6, 11) == nlp.resume_eval(6, 11)


def test_vacancy_gold_set_is_scored():
    report = nlp.vacancy_eval()
    assert report["n"] == 24
    assert 0.0 <= report["required"]["skills_f1"] <= 1.0
    assert set(report) >= {"role", "grade", "salary", "work_format", "city", "nice", "all_skills"}


def test_field_prf_counts_misses_and_wrong_values():
    assert nlp.field_prf([("a", "a"), (None, "b"), ("x", "c"), (None, None)]) == {"p": 0.5, "r": 0.333, "f1": 0.4}
    assert nlp.field_prf([(None, None)]) == {"p": 1.0, "r": 1.0, "f1": 1.0}


def test_held_out_vacancy_set_is_scored_separately():
    report = nlp.vacancy_eval("nlp_vacancies_holdout.json")
    assert report["n"] == 30
    assert set(report["fields_prf"]) == {"role", "grade", "salary", "work_format", "city"}

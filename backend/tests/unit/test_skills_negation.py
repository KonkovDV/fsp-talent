"""F-6a: a negated mention is not a skill (NegEx, Chapman et al. 2001, doi:10.1006/jbin.2001.1029)."""
from __future__ import annotations

import pytest

from app.services.skills import extract_skills, is_negated, quote_names_skill


def names(text: str) -> list[str]:
    return [s.skill for s in extract_skills(text)]


def test_dor_acceptance_example():
    assert names("Не работал с Kubernetes, хочу изучить Go. Опыт: Python") == ["Python"]


@pytest.mark.parametrize("text", [
    "Не работал с Kubernetes",
    "Не работала с Kubernetes",
    "Нет опыта с Kubernetes",
    "Нет опыта работы с Kubernetes",
    "Не знаком с Kubernetes",
    "Без Kubernetes",
    "Хочу изучить Kubernetes",
    "Планирую освоить Kubernetes",
    "No experience with Kubernetes",
    "Never used Kubernetes",
    "Not familiar with Kubernetes",
])
def test_negated_mention_is_skipped(text):
    assert "Kubernetes" not in names(text)


@pytest.mark.parametrize("text", [
    "Опыт: Kubernetes",
    "Не только Python, но и Kubernetes",
    "Не менее 3 лет с Kubernetes",
    "Не работал с Java, но Kubernetes знаю хорошо",
    "Нет опыта с Java. Kubernetes — 2 года",
    "Без отпусков: Kubernetes",
    "Не боюсь сложных задач, Kubernetes",
    "Работаю не первый год с Kubernetes",
    "Не новичок в Kubernetes",
    "Не раз настраивал Kubernetes",
    "Не один проект на Kubernetes",
    "No-code и Kubernetes",
    "Low-code, Kubernetes",
    "Работа без переработок с Kubernetes",
    "Не боюсь легаси на Kubernetes",
])
def test_plain_mention_after_a_clause_break_or_pseudo_negation_counts(text):
    assert "Kubernetes" in names(text)


def test_not_only_keeps_the_skill():
    assert "Python" in names("Не только Python, но и Go")


@pytest.mark.parametrize(("text", "expected"), [
    ("Работаю не первый год с Python", ["Python"]),
    ("Не новичок в Docker", ["Docker"]),
    ("Не раз настраивал Kubernetes", ["Kubernetes"]),
    ("No-code и Python", ["Python"]),
    ("Работа без переработок с Python и Django", ["Python", "Django"]),
])
def test_review_examples_keep_every_skill(text, expected):
    assert names(text) == expected


def test_without_negates_only_the_adjacent_word():
    assert "Docker" not in names("Деплой без Docker")
    assert "Docker" in names("Без лишней бюрократии деплоим в Docker")


def test_a_later_plain_mention_counts_and_offsets_point_at_it():
    text = "Не работал с Docker. Позже освоил Docker и Python."
    docker = next(s for s in extract_skills(text) if s.skill == "Docker")
    assert text[docker.start:docker.end] == "Docker" and docker.start > text.index("Позже")


def test_trigger_far_before_the_skill_does_not_negate():
    assert "Kubernetes" in names("Не люблю долго ждать сборки поэтому настроил Kubernetes")


def test_negation_helper_respects_clause_and_window():
    text = "Нет опыта, Kafka"
    assert not is_negated(text, text.index("Kafka"))
    text = "без Kafka"
    assert is_negated(text, text.index("Kafka"))


def test_a_negated_quote_does_not_confirm_the_skill():
    assert quote_names_skill("Kubernetes", "Kubernetes в проде 2 года")
    assert not quote_names_skill("Kubernetes", "не работал с Kubernetes")


def test_short_words_inside_other_words_are_not_triggers():
    assert "Kubernetes" in names("Нефтяная компания, Kubernetes")
    assert "Go" in names("Notebook, Go")

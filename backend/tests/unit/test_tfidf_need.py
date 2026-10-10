from app.services.need_draft import draft_need
from app.services.tfidf_need import suggest_skills

# Sentences that name a skill by an alias, not by a pasted canonical list.
HOLDOUT = (
    ("ищем человека на кафку и питон", {"Kafka", "Python"}),
    ("верстаем интерфейс на реакт и тайпскрипт", {"React", "TypeScript"}),
    ("нужен постгрес для платежей", {"PostgreSQL"}),
)


def test_holdout_suggestions_stay_inside_the_named_skills():
    hits = shown = 0
    for text, expected in HOLDOUT:
        got = suggest_skills(text)
        assert got, text
        hits += len(set(got) & expected)
        shown += len(got)
    assert hits / shown >= 0.8


def test_a_hint_is_not_saved_as_a_required_skill():
    draft = draft_need("Ищем человека на кафку, город не важен")
    assert "Kafka" not in draft["skills"]
    assert any("Похоже по словам" in line and "Kafka" in line for line in draft["notes"])

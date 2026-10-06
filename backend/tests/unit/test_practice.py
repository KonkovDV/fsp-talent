"""A short practice task shows the question and hides the answer key."""
import uuid
from datetime import UTC, datetime

from app.models.assessment import PracticeAttempt
from app.services.practice import public_attempt, resolve_practice_topic


def test_public_practice_item_has_no_answer_key():
    row = PracticeAttempt(
        id=uuid.uuid4(), participant_id=uuid.uuid4(), topic="sql", family_id="sql_query",
        stem="Сколько строк вернёт запрос?", code="SELECT 1", language="sql",
        options=["0", "1", "2", "3"], correct_index=1, explanation="Одна строка.",
        created_at=datetime.now(UTC),
    )
    payload = public_attempt(row)
    assert payload["options"][1]["text"] == "1"
    assert "correct_index" not in payload
    assert "explanation" not in payload
    assert payload["answered"] is False


def test_practice_uses_the_topic_the_candidate_asked_for():
    assert resolve_practice_topic("sql", None, from_vacancy=False) == "sql"
    assert resolve_practice_topic("не тема", None, from_vacancy=False) is None
    assert resolve_practice_topic("sql", "python", from_vacancy=True) == "python"

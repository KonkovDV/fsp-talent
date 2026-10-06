"""A short practice task shows the question and hides the answer key."""
import uuid
from datetime import UTC, datetime

from app.models.assessment import PracticeAttempt
from app.services.practice import public_attempt, resolve_practice_topic, same_practice_request


def _row(**extra) -> PracticeAttempt:
    fields = dict(
        id=uuid.uuid4(), participant_id=uuid.uuid4(), topic="sql", family_id="sql_query",
        stem="Сколько строк вернёт запрос?", code="SELECT 1", language="sql",
        options=["0", "1", "2", "3"], correct_index=1, explanation="Одна строка.",
        created_at=datetime.now(UTC),
    )
    fields.update(extra)
    return PracticeAttempt(**fields)


def test_numeric_practice_hides_the_answer():
    payload = public_attempt(_row())
    assert payload["answer_mode"] == "number"
    assert payload["options"] == []
    assert "correct_index" not in payload
    assert "explanation" not in payload
    assert payload["answered"] is False


def test_choice_practice_shows_options_without_the_key():
    payload = public_attempt(_row(
        options=["404 Not Found", "400 Bad Request", "410 Gone", "500 Internal Server Error"],
        correct_index=0,
    ))
    assert payload["answer_mode"] == "choice"
    assert [o["text"] for o in payload["options"]][0] == "404 Not Found"
    assert "correct_index" not in payload


def test_practice_uses_the_topic_the_candidate_asked_for():
    assert resolve_practice_topic("sql", None, from_vacancy=False) == "sql"
    assert resolve_practice_topic("не тема", None, from_vacancy=False) is None
    assert resolve_practice_topic("sql", "python", from_vacancy=True) == "python"


def test_an_open_task_is_kept_only_for_the_same_request():
    vacancy = uuid.uuid4()
    other = uuid.uuid4()
    assert same_practice_request("sql", None, "sql", None) is True
    assert same_practice_request("python", None, "sql", None) is False
    assert same_practice_request("sql", vacancy, None, vacancy) is True
    assert same_practice_request("sql", vacancy, None, other) is False
    assert same_practice_request("sql", vacancy, "sql", None) is False
    assert same_practice_request("python", None, None, None) is True

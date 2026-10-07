"""Guardian consent link: bound to the participant and to the exact email the minor named."""
import uuid

from app.services.guardian import guardian_token, token_participant, token_valid


def test_link_is_bound_to_the_person_and_the_email():
    pid = uuid.uuid4()
    token = guardian_token(pid, "Mama@Example.ru")
    assert token_participant(token) == pid
    assert token_valid(token, pid, "mama@example.ru")
    assert not token_valid(token, pid, "other@example.ru")
    assert not token_valid(token, uuid.uuid4(), "mama@example.ru")
    assert not token_valid(token, pid, None)
    assert token_participant("garbage") is None

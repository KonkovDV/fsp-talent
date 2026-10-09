"""Guardian consent link: bound to the participant and to the exact email the minor named."""
import uuid

from app.services.guardian import consent_link, guardian_token, token_participant, token_valid


def test_link_is_bound_to_the_person_and_the_email():
    pid = uuid.uuid4()
    token = guardian_token(pid, "Mama@Example.ru")
    assert token_participant(token) == pid
    assert token_valid(token, pid, "mama@example.ru")
    assert not token_valid(token, pid, "other@example.ru")
    assert not token_valid(token, uuid.uuid4(), "mama@example.ru")
    assert not token_valid(token, pid, None)
    assert token_participant("garbage") is None


def test_the_consent_link_keeps_the_token_out_of_the_query():
    link = consent_link("https://talent.example", "abc.def")
    assert link == "https://talent.example/guardian#token=abc.def"
    assert "?" not in link

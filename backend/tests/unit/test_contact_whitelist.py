"""The invitation contact is an e-mail, a Telegram @handle or an E.164 phone, nothing else."""
import pytest
from pydantic import ValidationError

from app.api.v1.offers import OfferCreate
from app.services.contact import contact_ok

GOOD = ["hr@sibcode.demo", "@sibcode_hr", "+79991234567", "+7 (999) 123-45-67", "hr@sibcode.demo, @sibcode_hr"]
BAD = ["t.me/x", "evil.ru/login", "bit.ly/abc", "https://evil.example/pay", "www.evil.ru", "@abc",
       "почта", "89991234567", "javascript:alert(1)", "hr@sibcode.demo, t.me/x", ""]


@pytest.mark.parametrize("value", GOOD)
def test_allowed_contacts(value):
    assert contact_ok(value)


@pytest.mark.parametrize("value", BAD)
def test_links_and_free_text_are_refused(value):
    assert not contact_ok(value)


def _offer(contact):
    return OfferCreate(candidate_id="11111111-1111-1111-1111-111111111111", salary_from_gross=100_000,
                       salary_to_gross=150_000, role="Backend", work_format="remote", contact_method=contact)


def test_the_api_model_answers_422_for_a_link_and_accepts_a_handle():
    assert _offer("@sibcode_hr").contact_method == "@sibcode_hr"
    with pytest.raises(ValidationError):
        _offer("bit.ly/abc")

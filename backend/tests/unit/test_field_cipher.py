"""Contact ciphertext does not repeat, does not travel between rows, and is not the login key."""
import uuid

import pytest

from app.models import Employer, Participant
from app.services.field_cipher import (
    FieldCipherError,
    _restore_obj,
    _seal_obj,
    blind_index,
    open_seal,
    seal,
)


def test_the_same_contact_seals_twice_and_opens_only_for_its_row():
    owner = str(uuid.uuid4())
    left = seal(owner, "participants", "email", "a@demo.talent")
    right = seal(owner, "participants", "email", "a@demo.talent")
    assert left != right
    assert left.startswith("enc:v1:")
    assert open_seal(owner, "participants", "email", left) == "a@demo.talent"
    with pytest.raises(FieldCipherError):
        open_seal(str(uuid.uuid4()), "participants", "email", left)
    with pytest.raises(FieldCipherError):
        open_seal(owner, "participants", "phone", left)


def test_the_login_key_is_stable_and_is_not_the_address():
    assert blind_index(" A@Demo.Talent ") == blind_index("a@demo.talent")
    assert blind_index("a@demo.talent") != "a@demo.talent"
    assert len(blind_index("a@demo.talent")) == 64


def test_a_flushed_contact_is_plaintext_again_in_memory():
    person = Participant(id=uuid.uuid4(), email="a@demo.talent", phone="+79990000000")
    _seal_obj(person)
    assert person.email.startswith("enc:v1:")
    assert person.email_bindex == blind_index("a@demo.talent")
    _restore_obj(person)
    assert person.email == "a@demo.talent"
    company = Employer(id=uuid.uuid4(), company_name="Сибкод", email="hr@demo.talent", password_hash="x")
    _seal_obj(company)
    assert company.email_bindex == blind_index("hr@demo.talent")
    _restore_obj(company)
    assert company.email == "hr@demo.talent"

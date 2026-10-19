"""Invitation moves stay inside one table."""
from types import SimpleNamespace

import pytest

from app.services.offer_flow import (
    TRANSITIONS,
    IllegalOfferMove,
    accept_counter,
    can_move,
    move_offer,
    record_counter,
)


def test_pending_reaches_each_terminal_once():
    for target in TRANSITIONS["pending"]:
        offer = SimpleNamespace(status="pending")
        assert can_move("pending", target)
        move_offer(offer, target)
        assert offer.status == target
        with pytest.raises(IllegalOfferMove):
            move_offer(offer, "pending")


def test_yes_if_stays_pending_and_keeps_contacts_closed():
    offer = SimpleNamespace(status="pending", counter_note=None, counter_at=None, contacts_revealed_at=None)
    note = record_counter(offer, "  Возьму,  если вилка от 280 тысяч  ")
    assert note == "Возьму, если вилка от 280 тысяч"
    assert offer.status == "pending" and offer.contacts_revealed_at is None
    assert offer.counter_note == note and offer.counter_at is not None
    with pytest.raises(ValueError):
        record_counter(offer, "мало")
    accepted = SimpleNamespace(status="accepted")
    with pytest.raises(IllegalOfferMove):
        record_counter(accepted, "Возьму, если вилка от 280 тысяч")


def test_company_accepts_the_condition_and_opens_contacts():
    offer = SimpleNamespace(
        status="pending", counter_note="Возьму, если вилка от 280 тысяч",
        counter_at=None, contacts_revealed_at=None, responded_at=None,
    )
    note = accept_counter(offer)
    assert note.startswith("Возьму")
    assert offer.status == "accepted"
    assert offer.contacts_revealed_at is not None and offer.responded_at == offer.contacts_revealed_at
    bare = SimpleNamespace(status="pending", counter_note=None)
    with pytest.raises(ValueError):
        accept_counter(bare)
    done = SimpleNamespace(status="accepted", counter_note="Возьму, если вилка от 280 тысяч")
    with pytest.raises(IllegalOfferMove):
        accept_counter(done)


def test_unknown_state_does_not_move():
    offer = SimpleNamespace(status="closed")
    with pytest.raises(IllegalOfferMove):
        move_offer(offer, "accepted")
    assert offer.status == "closed"

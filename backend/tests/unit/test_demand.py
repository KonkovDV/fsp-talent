"""Demand figures stay anonymous, and a company's own refusals are counted apart from the market."""
import uuid

from app.services.demand import invite_band, view_ids_to_note
from app.services.market import own_reason_counts


def test_the_invitation_band_stays_hidden_below_five():
    assert invite_band([(100_000, 200_000)] * 4) is None
    band = invite_band([
        (100_000, 140_000),
        (120_000, 180_000),
        (200_000, 260_000),
        (80_000, 100_000),
        (150_000, 190_000),
    ])
    assert band == {"n": 5, "median_from": 120_000, "median_to": 180_000}


def test_a_repeat_view_the_same_day_is_not_noted_again():
    first, second = uuid.uuid4(), uuid.uuid4()
    assert view_ids_to_note({first}, [first, second, second]) == [second]


def test_own_refusals_count_from_the_first_answer():
    assert own_reason_counts([]) is None
    assert own_reason_counts(["salary", "unknown", "format"]) == {
        "n": 2, "counts": {"salary": 1, "format": 1},
    }

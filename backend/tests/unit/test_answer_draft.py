import pytest

from app.services.answer_draft import DraftBoth, DraftStale, apply_draft


def test_the_first_save_stores_the_choice_and_bumps_the_version():
    assert apply_draft(0, 0, 2, None) == (1, 2, None)


def test_a_stale_tab_does_not_overwrite_a_newer_draft():
    with pytest.raises(DraftStale):
        apply_draft(2, 1, 0, None)


def test_a_choice_and_a_number_together_are_refused():
    with pytest.raises(DraftBoth):
        apply_draft(0, 0, 1, "4")

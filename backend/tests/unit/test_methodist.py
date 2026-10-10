from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services.staff import release_key


def test_release_returns_the_key_and_refuses_a_note_with_an_email():
    row = SimpleNamespace(status="quarantined", quarantined_at=datetime.now(UTC), updated_at=None)
    release_key(row, "ложное срабатывание на чистых ответах", datetime.now(UTC))
    assert row.status == "active" and row.quarantined_at is None
    with pytest.raises(ValueError):
        release_key(SimpleNamespace(status="quarantined"), "пишите на hr@example.com", datetime.now(UTC))


def test_an_active_key_is_not_released_again():
    with pytest.raises(ValueError):
        release_key(SimpleNamespace(status="active"), "заметка", datetime.now(UTC))

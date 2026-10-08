"""A finished exam and an invitation drop the cached shortlist. A trial does not."""
import pytest

from app.services.search import cache


@pytest.mark.asyncio
async def test_a_real_exam_drops_the_shortlist_and_a_trial_does_not(monkeypatch):
    calls = []

    async def fake_bump() -> None:
        calls.append("bump")

    monkeypatch.setattr(cache, "bump_bank_epoch", fake_bump)
    await cache.publish_grade(trial=False)
    await cache.publish_grade(trial=True)
    await cache.publish_invite()
    assert calls == ["bump", "bump"]

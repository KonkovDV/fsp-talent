"""The shortlist cache keeps one ranking and drops it after a real exam or an invitation."""
import pytest

from app.services.search import cache


def test_page_comes_from_one_ranking_not_a_separate_window():
    stored = cache.store_payload({
        "total": 1000,
        "items": [{"candidate_id": str(i), "shortlisted": True, "invited": True} for i in range(10)],
    })
    assert stored["complete"] is True
    assert "shortlisted" not in stored["ranked"][0]
    assert "invited" not in stored["ranked"][0]
    page = cache.slice_ranked(stored, 0, 4)
    assert [item["candidate_id"] for item in page["items"]] == ["0", "1", "2", "3"]
    page["items"][0]["invited"] = True
    assert "invited" not in stored["ranked"][0]


def test_a_truncated_window_does_not_serve_a_page_past_its_end():
    stored = {"ranked": [{"candidate_id": "1"}], "complete": False, "total": 1000}
    assert cache.slice_ranked(stored, 0, 1)["items"][0]["candidate_id"] == "1"
    assert cache.slice_ranked(stored, 20, 20) is None


def test_company_marks_are_this_companys_only():
    cards = [{"candidate_id": "a"}, {"candidate_id": "b"}]
    cache.apply_company_marks(
        cards, {"a"}, {"a": {"invited": True, "contacts_closed": True}})
    assert cards[0]["shortlisted"] is True
    assert cards[0]["invited"] is True
    assert cards[0]["contacts_closed"] is True
    assert cards[1]["invited"] is False
    other = [{"candidate_id": "a"}, {"candidate_id": "b"}]
    cache.apply_company_marks(other, set(), {})
    assert other[0]["invited"] is False and other[0]["contacts_closed"] is False
    assert other[0]["shortlisted"] is False


def test_epoch_changes_the_key_and_identical_needs_share_one():
    assert cache.shortlist_key("n", 3, 1) != cache.shortlist_key("n", 3, 2)
    params = {"role": "backend", "skills": ["Python"]}
    assert cache.shared_key(params, 4) == cache.shared_key({"skills": ["Python"], "role": "backend"}, 4)
    assert cache.shared_key(params, 4) != cache.shared_key(params, 5)


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def incr(self, key):
        self.data[key] = str(int(self.data.get(key) or 0) + 1)
        return int(self.data[key])

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True


@pytest.mark.asyncio
async def test_bump_drops_the_previous_ranking(monkeypatch):
    redis = _Redis()

    async def get():
        return redis

    monkeypatch.setattr(cache, "get_redis", get)
    payload = cache.store_payload({"total": 1, "items": [{"candidate_id": "a"}]})
    epoch = await cache.bank_epoch(redis)
    await cache.write_ranked(redis, cache.shortlist_key("n", 1, epoch), payload)
    await cache.bump_bank_epoch()
    assert await cache.bank_epoch(redis) == epoch + 1
    assert await cache.read_ranked(redis, cache.shortlist_key("n", 1, epoch + 1)) is None


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

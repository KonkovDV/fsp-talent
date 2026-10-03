import pytest
from app.services.fsp.mock import MockFSPAdapter


@pytest.mark.asyncio
async def test_demo_profiles_and_deterministic_generator():
    adapter = MockFSPAdapter()
    demo = await adapter.fetch_participant("FSP001")
    assert demo is not None
    assert demo.birth_date.year == 2003
    assert demo.results[0].competition_status == "russia_championship"
    first = await adapter.fetch_participant("FSP1000")
    second = await adapter.fetch_participant("FSP1000")
    assert first.display_name == second.display_name
    assert [(r.event_id, r.place) for r in first.results] == [(r.event_id, r.place) for r in second.results]
    assert await adapter.fetch_participant("NOPE") is None
    assert await adapter.verify_secret("FSP1000", "test")
    assert not await adapter.verify_secret("FSP1000", "wrong")

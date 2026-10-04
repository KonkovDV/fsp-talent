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


@pytest.mark.asyncio
async def test_generator_range_matches_readme():
    """README and seed: FSP1000-FSP1149. Anything outside must not authenticate with the demo secret."""
    adapter = MockFSPAdapter()
    assert await adapter.fetch_participant("FSP1149") is not None
    for fsp_id in ("FSP999", "FSP1150", "FSP1999"):
        assert await adapter.fetch_participant(fsp_id) is None
        assert not await adapter.verify_secret(fsp_id, "test")


@pytest.mark.asyncio
async def test_generated_results_respect_db_checks():
    """Synthetic protocols must satisfy the CHECK constraints from migration 0002."""
    adapter = MockFSPAdapter()
    for n in range(1000, 1150):
        participant = await adapter.fetch_participant(f"FSP{n}")
        for r in participant.results:
            assert 1 <= r.place <= r.total_participants
            assert r.team_size >= 1

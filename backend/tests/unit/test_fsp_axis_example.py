"""The example from the pitch: twenty entries without a result do not outweigh two wins (FSP axis v3)."""
from datetime import date

from app.services.scoring.engine import compute_discipline_score

REF = date(2026, 10, 1)


def _events(n: int, place: int) -> list[dict]:
    return [dict(id=f"e{i}", place=place, total_participants=100, competition_status="regional", team_size=1,
                 event_date=date(2026, 6, 1)) for i in range(n)]


def test_twenty_entries_in_the_lower_half_stay_below_two_wins():
    entries = compute_discipline_score(_events(20, 60), REF)
    wins = compute_discipline_score(_events(2, 1), REF)
    assert round(entries["lcb"], 2) == 0.16   # v4: lower-half entries are not results; empty-history bound
    assert round(wins["lcb"], 2) == 0.52

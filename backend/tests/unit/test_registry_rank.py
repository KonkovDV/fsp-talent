"""A rank is a registry fact. The demo registry applies the age gates; the score does not."""
from datetime import date
from types import SimpleNamespace

from app.api.v1.candidates import discipline_score_view
from app.services.fsp.mock import FSPParticipant, FSPResult, demo_rank, demo_ranks
from app.services.fsp.registry import parse_participant
from app.services.scoring.engine import RANK_ORDER, rank_at_least


def _person(birth: date, place: int, status: str = "russia_championship") -> FSPParticipant:
    return FSPParticipant("FSP9", "Тест", "Москва", birth, "m", [
        FSPResult("ev", "Чемпионат", "algorithmic", status, place, 100, False, 1, date(2026, 8, 1)),
    ])


def test_a_fifteen_year_old_champion_of_russia_is_kms_not_master():
    person = _person(date(2011, 1, 1), 1)
    assert demo_rank("russia_championship", 1, 15) == "КМС"
    ranks = demo_ranks(person)
    assert ranks[0].rank == "КМС"
    assert ranks[0].order_ref.startswith("Приказ-демо-")


def test_second_place_at_the_russian_championship_is_kms_not_master():
    assert demo_rank("russia_championship", 2, 22) == "КМС"
    assert demo_rank("russia_championship", 1, 22) == "МС"


def test_profile_view_returns_the_registry_fields():
    row = SimpleNamespace(
        discipline="algorithmic", score=0.5, sigma=0.1, lcb=0.4, confidence=0.5,
        best_rank="КМС", events_count=2, rank_assigned_at=date(2025, 11, 20),
        rank_order_ref="Приказ-демо-2025-1",
    )
    view = discipline_score_view(row)
    assert view["best_rank"] == "КМС"
    assert view["rank_assigned_at"] == "2025-11-20"
    assert view["rank_order_ref"] == "Приказ-демо-2025-1"


def test_kms_filter_keeps_master_and_candidate_master_only():
    allowed = RANK_ORDER[:RANK_ORDER.index("КМС") + 1]
    assert allowed == ["МС", "КМС"]
    assert rank_at_least("МС", "КМС") and rank_at_least("КМС", "КМС")
    assert not rank_at_least("I", "КМС")


def test_a_protocol_link_that_is_not_http_is_dropped():
    base = {
        "event_id": "e1", "event_name": "Кубок", "discipline": "algorithmic",
        "competition_status": "regional", "place": 2, "total_participants": 40, "event_date": "2025-06-01",
    }
    person = {
        "fsp_id": "FSP9", "display_name": "Тест", "region": "Москва", "birth_date": "2004-01-01", "ranks": [],
    }
    kept = parse_participant({**person, "results": [{**base, "protocol_url": "https://fsp.ru/p/1"}]})
    dropped = parse_participant({**person, "results": [{**base, "protocol_url": "javascript:alert(1)"}]})
    assert kept.results[0].protocol_url == "https://fsp.ru/p/1"
    assert dropped.results[0].protocol_url is None


def test_the_registry_contract_drops_an_unknown_rank():
    person = parse_participant({
        "fsp_id": "FSP9", "display_name": "Тест", "region": "Москва", "birth_date": "2004-01-01",
        "results": [],
        "ranks": [
            {"discipline": "algorithmic", "rank": "МСМК", "assigned_at": "2025-01-01", "order_ref": "нет"},
            {"discipline": "algorithmic", "rank": "КМС", "assigned_at": "2025-06-01", "order_ref": "Приказ-1"},
        ],
    })
    assert [row.rank for row in person.ranks] == ["КМС"]

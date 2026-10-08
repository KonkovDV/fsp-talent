"""
FSP integration adapters.

MockFSPAdapter serves two hand-written demo profiles (FSP001, FSP002) and deterministically
generates synthetic protocols for FSP1000..FSP1149 (the range the seed script loads as profiles) and
FSP2000..FSP2099 (athletes who exist in the mock registry but have no account yet: use them to demo
linking an FSP account to an email registration). Same id -> same data. Other ids are rejected.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from app.core.config import settings

TEAM_DISCIPLINES = {"product", "security", "bas", "robotics"}
GENERATED_RANGE = range(1000, 1150)
UNCLAIMED_RANGE = range(2000, 2100)
DEMO_SECRET = "test"

# Event names. The score does not use the status; these words are only for the protocol line.
STATUS_LABELS = {
    "world": "Чемпионат/первенство мира",
    "russia_championship": "Чемпионат России",
    "russia_cup": "Кубок России",
    "russia_youth": "Первенство России",
    "all_russian": "Всероссийские соревнования",
    "federal_district": "Соревнования федерального округа",
    "regional": "Соревнования субъекта РФ",
    "other": "Прочие соревнования",
}

# Demo registry only. The table follows order of the Ministry of Sport No. 6 (revision of 22.04.2024).
# Reconcile it with appendix No. 77 to order No. 299 of 09.04.2026 before treating the numbers as current.
# The cup split «МС за 1, КМС за 2–3» is the reading of an ambiguous 2024 line. Youth ranks are the only
# outcome of events outside that table. Age must be reached before the first day of the event:
# МС from 16, КМС from 15, I–III from 14, youth ranks from 12. МСМК is not in the sport's norms.
_DEMO_RANK_TABLE: dict[str, list[tuple[int, str]]] = {
    "world": [(1, "МС"), (8, "КМС")],
    "russia_championship": [(1, "МС"), (4, "КМС"), (9, "I")],
    "russia_cup": [(1, "МС"), (3, "КМС"), (8, "I")],
    "russia_youth": [(1, "КМС"), (8, "I")],
    "all_russian": [(2, "I")],
    "federal_district": [(2, "I"), (4, "II"), (8, "III")],
    "regional": [(2, "I"), (4, "II"), (6, "III")],
    "other": [(1, "I юн."), (2, "II юн."), (6, "III юн.")],
}
_RANK_AGE = {"МС": 16, "КМС": 15, "I": 14, "II": 14, "III": 14, "I юн.": 12, "II юн.": 12, "III юн.": 12}


@dataclass
class FSPResult:
    event_id: str
    event_name: str
    discipline: str
    competition_status: str
    place: int
    total_participants: int
    is_team: bool
    team_size: int
    event_date: date
    regions_count: int | None = None
    role: str = "participant"
    protocol_url: str | None = None
    trust_level: str = "verified_fsp"
    # Demo calendar id. A real registry may send its own; the «ЕКП-демо-» prefix is not a ministry record.
    ekp_number: str | None = None


@dataclass
class RegistryRank:
    """A rank assigned by an order, not derived from one place."""
    discipline: str
    rank: str
    assigned_at: date
    order_ref: str


@dataclass
class FSPParticipant:
    fsp_id: str
    display_name: str
    region: str
    birth_date: date
    gender: str | None = None   # used only to generate demo names; the registry contract does not ask for it
    results: list[FSPResult] = field(default_factory=list)
    ranks: list[RegistryRank] = field(default_factory=list)


@dataclass(frozen=True)
class FSPChanges:
    fsp_ids: list[str]
    next_since: datetime


class FSPAdapter(Protocol):
    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None: ...

    async def changes_since(self, since: datetime) -> FSPChanges: ...


DEMO: dict[str, FSPParticipant] = {
    "FSP001": FSPParticipant("FSP001", "Алексей Иванов", "Москва", date(2003, 5, 12), "m", [
        FSPResult("CR2025-ALG", "Чемпионат России по спортивному программированию 2025", "algorithmic",
                  "russia_championship", 3, 180, False, 1, date(2025, 11, 20), 52,
                  ekp_number="ЕКП-демо-2025-0001"),
        FSPResult("KR2025-ALG", "Кубок России 2025, алгоритмическое", "algorithmic",
                  "russia_cup", 6, 140, False, 1, date(2025, 4, 18), 40,
                  ekp_number="ЕКП-демо-2025-0002"),
        FSPResult("CR2025-PRD", "Чемпионат России 2025, продуктовое", "product",
                  "russia_championship", 2, 64, True, 4, date(2025, 10, 5), 30,
                  ekp_number="ЕКП-демо-2025-0003"),
    ]),
    "FSP002": FSPParticipant("FSP002", "Мария Петрова", "Санкт-Петербург", date(2001, 9, 3), "f", [
        FSPResult("CR2025-IB", "Чемпионат России 2025, системы ИБ", "security",
                  "russia_championship", 1, 90, True, 4, date(2025, 12, 2), 35,
                  ekp_number="ЕКП-демо-2025-0004"),
        FSPResult("VS2024-BAS", "Всероссийские соревнования по БАС 2024", "bas",
                  "all_russian", 5, 38, True, 3, date(2024, 9, 14), 18,
                  ekp_number="ЕКП-демо-2024-0005"),
    ]),
}

_FIRST_M = ["Алексей", "Дмитрий", "Иван", "Артём", "Никита", "Михаил", "Егор", "Кирилл", "Максим", "Тимур"]
_FIRST_F = ["Анна", "Мария", "Екатерина", "Софья", "Дарья", "Полина", "Алина", "Виктория", "Ксения", "Елена"]
_LAST = ["Смирнов", "Кузнецов", "Попов", "Васильев", "Соколов", "Морозов", "Волков", "Лебедев", "Козлов",
         "Новиков", "Фёдоров", "Орлов", "Зайцев", "Павлов", "Семёнов"]
_REGIONS = ["Москва", "Санкт-Петербург", "Новосибирская область", "Республика Татарстан",
            "Свердловская область", "Нижегородская область", "Самарская область",
            "Томская область", "Краснодарский край", "Чувашская Республика",
            "Приморский край", "Пермский край"]
_STATUSES = [("russia_championship", 0.12), ("russia_cup", 0.10), ("russia_youth", 0.10),
             ("all_russian", 0.18), ("federal_district", 0.18), ("regional", 0.22), ("other", 0.10)]
_FIELD_SIZE = {"russia_championship": (60, 220), "russia_cup": (40, 160), "russia_youth": (40, 160),
               "all_russian": (30, 140), "federal_district": (20, 90), "regional": (10, 60), "other": (8, 40)}
_DISC_LABEL = {"algorithmic": "алгоритмическое", "product": "продуктовое",
               "security": "системы ИБ", "bas": "БАС", "robotics": "робототехника"}


def _generate(fsp_id: str) -> FSPParticipant:
    n = int(fsp_id[3:])
    rng = random.Random(n)
    gender = rng.choice("mf")
    first = rng.choice(_FIRST_M if gender == "m" else _FIRST_F)
    last = rng.choice(_LAST) + ("" if gender == "m" else "а")
    today = date.today()
    age = rng.choice([15, 16, 17]) if rng.random() < 0.15 else rng.randint(18, 30)
    birth = today - timedelta(days=age * 365 + rng.randint(0, 364))
    skill = rng.gauss(0, 1)  # latent ability drives places consistently across events
    disciplines = rng.sample(list(_DISC_LABEL), k=rng.choice([1, 1, 2]))
    results = []
    for i in range(rng.randint(1, 6)):
        disc = rng.choice(disciplines)
        status = rng.choices([s for s, _ in _STATUSES], weights=[w for _, w in _STATUSES])[0]
        lo, hi = _FIELD_SIZE[status]
        total = rng.randint(lo, hi)
        pct = min(0.999, max(0.001, 0.5 + 0.28 * (skill + rng.gauss(0, 0.6))))
        place = max(1, min(total, round((1 - pct) * total)))
        team = disc in TEAM_DISCIPLINES
        ev_date = today - timedelta(days=rng.randint(20, 4 * 365))
        results.append(FSPResult(
            event_id=f"{status[:6].upper()}-{ev_date.year}-{disc[:3].upper()}-{n}-{i}",
            event_name=f"{_status_name(status)} {ev_date.year}, {_DISC_LABEL[disc]}",
            discipline=disc, competition_status=status, place=place, total_participants=total,
            is_team=team, team_size=rng.choice([2, 3, 4, 5]) if team else 1, event_date=ev_date,
            regions_count=max(1, total // rng.randint(3, 6)),
            ekp_number=f"ЕКП-демо-{ev_date.year}-{n:04d}-{i}",
        ))
    person = FSPParticipant(fsp_id, f"{first} {last}", rng.choice(_REGIONS), birth, gender, results)
    person.ranks = demo_ranks(person)
    return person


def _age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def demo_rank(status: str, place: int, age: int) -> str | None:
    """The rank a demo registry would record. None when the table or the age gives nothing."""
    from app.services.scoring.engine import RANK_ORDER

    raw = None
    for max_place, rank in _DEMO_RANK_TABLE.get(status, ()):
        if place <= max_place:
            raw = rank
            break
    if raw is None:
        return None
    for candidate in RANK_ORDER[RANK_ORDER.index(raw):]:
        if age >= _RANK_AGE[candidate]:
            return candidate
    return None


def demo_ranks(person: FSPParticipant) -> list[RegistryRank]:
    """One rank per discipline: the strongest, and the earlier order when two events tie."""
    from app.services.scoring.engine import RANK_ORDER

    chosen: dict[str, tuple[int, date, str, RegistryRank]] = {}
    for index, row in enumerate(person.results, start=1):
        rank = demo_rank(row.competition_status, row.place, _age_on(person.birth_date, row.event_date))
        if rank is None:
            continue
        fact = RegistryRank(row.discipline, rank, row.event_date, f"Приказ-демо-{row.event_date.year}-{index}")
        key = (RANK_ORDER.index(rank), row.event_date, row.event_id)
        prev = chosen.get(row.discipline)
        if prev is None or key < prev[:3]:
            chosen[row.discipline] = (*key, fact)
    return [item[3] for item in chosen.values()]


def choose_registry_ranks(ranks: list[RegistryRank]) -> dict[str, RegistryRank]:
    """Strongest rank per discipline. An earlier order wins a tie."""
    from app.services.scoring.engine import RANK_ORDER

    chosen: dict[str, RegistryRank] = {}
    for fact in ranks:
        if fact.rank not in RANK_ORDER:
            continue
        prev = chosen.get(fact.discipline)
        if prev is None or RANK_ORDER.index(fact.rank) < RANK_ORDER.index(prev.rank) or (
            fact.rank == prev.rank and fact.assigned_at < prev.assigned_at
        ):
            chosen[fact.discipline] = fact
    return chosen


def _status_name(status: str) -> str:
    return STATUS_LABELS[status]


for _person in DEMO.values():
    _person.ranks = demo_ranks(_person)


class MockFSPAdapter:
    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None:
        if fsp_id in DEMO:
            return DEMO[fsp_id]
        number = int(fsp_id[3:]) if fsp_id.startswith("FSP") and fsp_id[3:].isdigit() else -1
        if number in GENERATED_RANGE or number in UNCLAIMED_RANGE:
            return _generate(fsp_id)
        return None

    async def changes_since(self, since: datetime) -> FSPChanges:
        """Ids whose latest protocol line is on or after `since`. Demo data only."""
        moment = since.date() if isinstance(since, datetime) else since
        found: list[str] = []
        for fsp_id, person in DEMO.items():
            if any(row.event_date >= moment for row in person.results):
                found.append(fsp_id)
        for number in (*GENERATED_RANGE, *UNCLAIMED_RANGE):
            person = _generate(f"FSP{number}")
            if any(row.event_date >= moment for row in person.results):
                found.append(person.fsp_id)
        return FSPChanges(found, datetime.now(UTC))

    async def verify_secret(self, fsp_id: str, secret: str) -> bool:
        return secret == DEMO_SECRET and await self.fetch_participant(fsp_id) is not None


def get_fsp_adapter() -> FSPAdapter:
    if settings.FSP_MODE == "real":
        from app.services.fsp.registry import HttpFSPAdapter
        return HttpFSPAdapter()
    return MockFSPAdapter()

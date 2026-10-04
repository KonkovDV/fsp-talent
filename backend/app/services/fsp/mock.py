"""
FSP integration adapters.

MockFSPAdapter serves two hand-written demo profiles (FSP001, FSP002) and deterministically
generates synthetic protocols for FSP1000..FSP1149 (exactly the range the seed script loads and
the README documents). Same id -> same data. Ids outside the range are rejected, so nobody can
register unseeded synthetic identities with the public demo secret.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol

from app.core.config import settings

TEAM_DISCIPLINES = {"product", "security", "bas", "robotics"}
GENERATED_RANGE = range(1000, 1150)
DEMO_SECRET = "test"


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


@dataclass
class FSPParticipant:
    fsp_id: str
    display_name: str
    region: str
    birth_date: date
    gender: str
    results: list[FSPResult] = field(default_factory=list)


class FSPAdapter(Protocol):
    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None: ...
    async def verify_secret(self, fsp_id: str, secret: str) -> bool: ...


DEMO: dict[str, FSPParticipant] = {
    "FSP001": FSPParticipant("FSP001", "Алексей Иванов", "Москва", date(2003, 5, 12), "m", [
        FSPResult("CR2025-ALG", "Чемпионат России по спортивному программированию 2025", "algorithmic",
                  "russia_championship", 3, 180, False, 1, date(2025, 11, 20), 52,
                  protocol_url="https://fsp-russia.ru/protocols/CR2025-ALG"),
        FSPResult("KR2025-ALG", "Кубок России 2025, алгоритмическое", "algorithmic",
                  "russia_cup", 6, 140, False, 1, date(2025, 4, 18), 40),
        FSPResult("CR2025-PRD", "Чемпионат России 2025, продуктовое", "product",
                  "russia_championship", 2, 64, True, 4, date(2025, 10, 5), 30),
    ]),
    "FSP002": FSPParticipant("FSP002", "Мария Петрова", "Санкт-Петербург", date(2001, 9, 3), "f", [
        FSPResult("CR2025-IB", "Чемпионат России 2025, системы ИБ", "security",
                  "russia_championship", 1, 90, True, 4, date(2025, 12, 2), 35,
                  protocol_url="https://fsp-russia.ru/protocols/CR2025-IB"),
        FSPResult("VS2024-BAS", "Всероссийские соревнования по БАС 2024", "bas",
                  "all_russian", 5, 38, True, 3, date(2024, 9, 14), 18),
    ]),
}

_FIRST_M = ["Алексей", "Дмитрий", "Иван", "Артём", "Никита", "Михаил", "Егор", "Кирилл", "Максим", "Тимур"]
_FIRST_F = ["Анна", "Мария", "Екатерина", "Софья", "Дарья", "Полина", "Алина", "Виктория", "Ксения", "Елена"]
_LAST = ["Смирнов", "Кузнецов", "Попов", "Васильев", "Соколов", "Морозов", "Волков", "Лебедев", "Козлов",
         "Новиков", "Фёдоров", "Орлов", "Зайцев", "Павлов", "Семёнов"]
_REGIONS = ["Москва", "Санкт-Петербург", "Новосибирская область", "Республика Татарстан", "Свердловская область",
            "Нижегородская область", "Самарская область", "Томская область", "Краснодарский край",
            "Чувашская Республика", "Приморский край", "Пермский край"]
_STATUSES = [("russia_championship", 0.12), ("russia_cup", 0.10), ("russia_youth", 0.10), ("all_russian", 0.18),
             ("federal_district", 0.18), ("regional", 0.22), ("other", 0.10)]
_FIELD_SIZE = {"russia_championship": (60, 220), "russia_cup": (40, 160), "russia_youth": (40, 160),
               "all_russian": (30, 140), "federal_district": (20, 90), "regional": (10, 60), "other": (8, 40)}
_DISC_LABEL = {"algorithmic": "алгоритмическое", "product": "продуктовое", "security": "системы ИБ",
               "bas": "БАС", "robotics": "робототехника"}


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
        ))
    return FSPParticipant(fsp_id, f"{first} {last}", rng.choice(_REGIONS), birth, gender, results)


def _status_name(status: str) -> str:
    from app.services.scoring.engine import STATUS_LABELS
    return STATUS_LABELS[status]


class MockFSPAdapter:
    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None:
        if fsp_id in DEMO:
            return DEMO[fsp_id]
        if fsp_id.startswith("FSP") and fsp_id[3:].isdigit() and int(fsp_id[3:]) in GENERATED_RANGE:
            return _generate(fsp_id)
        return None

    async def verify_secret(self, fsp_id: str, secret: str) -> bool:
        return secret == DEMO_SECRET and await self.fetch_participant(fsp_id) is not None


class RealFSPAdapter:
    """Placeholder until the FSP API specification is provided by the case holder."""

    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None:
        raise NotImplementedError("FSP API specification not available yet")

    async def verify_secret(self, fsp_id: str, secret: str) -> bool:
        raise NotImplementedError("FSP API specification not available yet")


def get_fsp_adapter() -> FSPAdapter:
    return RealFSPAdapter() if settings.FSP_MODE == "real" else MockFSPAdapter()

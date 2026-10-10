import json
import uuid
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import needs
from app.services.ai import providers, second_opinion
from app.services.ai.second_opinion import facts, parse

CARD = {
    "candidate_id": "00000000-0000-0000-0000-0000000000c1",
    "role": "backend",
    "grade": "middle",
    "grade_source": "assessed",
    "region": "Новосибирск",
    "experience_years": 3,
    "resume_summary": "Иван Петров, ivan@example.com",
    "matched_skills": ["Python", "SQL"],
    "missing_skills": ["Kafka"],
    "stack": ["Python", "Docker"],
    "disciplines": [{"label": "Продуктовое программирование", "events_count": 4, "best_rank": "КМС"}],
    "match": {"plus": ["Грейд совпадает"], "minus": ["Нет Kafka"], "info": ["Живёт в городе Новосибирск"]},
    "why": ["Навыки: 2 из 3 (Python, SQL)"],
}
NEED = {"role": "backend", "grade": "middle", "skills": ["Kafka", "Python", "SQL"], "nice_to_have": []}


def test_facts_keep_the_card_and_drop_identity():
    known = facts(CARD, NEED)
    text = "\n".join(known)
    assert "Kafka" in text and "КМС" in text and "подтверждён тестом" in text
    for leak in ("Новосибирск", "Иван", "ivan@", "0000000000c1"):
        assert leak not in text
    assert facts(CARD, NEED) == known


def test_parse_keeps_only_grounded_points():
    known = facts(CARD, NEED)
    i_skills = next(i for i, f in enumerate(known, 1) if f.startswith("Навыки: 2 из 3"))
    i_missing = next(i for i, f in enumerate(known, 1) if f.startswith("Нет из обязательных"))
    answer = json.dumps({
        "summary": "Мидл с подтверждённым грейдом, не хватает Kafka.",
        "strengths": [
            {"text": "Два из трёх навыков, 2 из 3", "facts": [i_skills]},
            {"text": "Пять лет опыта: 5", "facts": [i_skills]},
            {"text": "Без ссылки", "facts": []},
            {"text": "Чужой факт", "facts": [99]},
            {"text": "Подходит по возрасту", "facts": [i_skills]},
        ],
        "risks": [{"text": "Нет Kafka", "facts": [i_missing]}],
        "questions": [{"text": "Был ли опыт с очередями сообщений?", "facts": [i_missing]}],
    }, ensure_ascii=False)
    note, dropped = parse("Вот ответ: " + answer, known)
    assert [p["text"] for p in note["strengths"]] == ["Два из трёх навыков, 2 из 3"]
    assert note["strengths"][0]["facts"] == [known[i_skills - 1]]
    assert note["risks"][0]["text"] == "Нет Kafka"
    assert len(note["questions"]) == 1
    assert note["summary"].startswith("Мидл")
    assert dropped == 4


def test_parse_survives_garbage_and_blanks_a_biased_summary():
    known = facts(CARD, NEED)
    assert parse("не JSON", known) == ({"strengths": [], "risks": [], "questions": [], "summary": ""}, 0)
    note, dropped = parse(json.dumps({"summary": "Молодой специалист из 7 команд"}, ensure_ascii=False), known)
    assert note["summary"] == "" and dropped == 1


async def test_second_opinion_marks_itself_advisory(monkeypatch):
    seen = {}

    async def fake_chat(provider, model, system, user, **kw):
        seen["user"] = user
        return '{"summary": "Кратко", "strengths": [], "risks": [], "questions": []}'

    monkeypatch.setattr(providers, "active", lambda: SimpleNamespace(kind="yandex", model="yandexgpt/latest"))
    monkeypatch.setattr(providers, "chat", fake_chat)
    note = await second_opinion.second_opinion(CARD, NEED)
    assert note["advisory"] is True and note["affects_score"] is False
    assert note["provider"] == "yandex" and note["summary"] == "Кратко"
    assert "Новосибирск" not in seen["user"] and "ivan@" not in seen["user"]


async def test_second_opinion_needs_a_provider(monkeypatch):
    monkeypatch.setattr(providers, "active", lambda: None)
    with pytest.raises(providers.ProviderError):
        await second_opinion.second_opinion(CARD, NEED)


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value


def _wire(monkeypatch, *, provider=True, items=(CARD,), limited=False):
    need = SimpleNamespace(id=uuid.uuid4(), version=1, employer_id=uuid.uuid4())
    redis, calls = _Redis(), []

    async def own(db, need_id, current):
        return need

    async def params(db, n):
        return SimpleNamespace(params={"role": "backend", "grade": "middle", "skills": ["Python", "SQL", "Kafka"]})

    async def matches(db, n, p, limit, offset):
        return {"items": [dict(c) for c in items]}

    async def hydrate(db, page):
        return page

    async def refresh(db=None):
        return object() if provider else None

    async def rate(*a, **kw):
        return limited

    async def rds():
        return redis

    async def opinion(card, need_facts):
        calls.append(card["candidate_id"])
        return {"summary": "ok", "strengths": [], "risks": [], "questions": [], "dropped": 0,
                "provider": "yandex", "advisory": True, "affects_score": False}

    for name, fn in (("_own", own), ("_params", params), ("_matches_cached", matches), ("_hydrate", hydrate),
                     ("too_many", rate), ("_redis", rds)):
        monkeypatch.setattr(needs, name, fn)
    monkeypatch.setattr(needs.providers, "refresh", refresh)
    monkeypatch.setattr(needs.second_opinion, "second_opinion", opinion)
    return calls


async def test_endpoint_caches_the_note(monkeypatch):
    calls = _wire(monkeypatch)
    current = {"sub": str(uuid.uuid4())}
    first = await needs.ai_note(uuid.uuid4(), _cid(), current, None)
    second = await needs.ai_note(uuid.uuid4(), _cid(), current, None)
    assert first["cached"] is False and second["cached"] is True
    assert calls == [str(_cid())]


def _cid():
    return uuid.UUID("00000000-0000-0000-0000-0000000000c1")


@pytest.mark.parametrize("kw, status", [({"provider": False}, 503), ({"items": ()}, 404), ({"limited": True}, 429)])
async def test_endpoint_refuses(monkeypatch, kw, status):
    _wire(monkeypatch, **kw)
    with pytest.raises(ApiError) as e:
        await needs.ai_note(uuid.uuid4(), _cid(), {"sub": "e1"}, None)
    assert e.value.status_code == status

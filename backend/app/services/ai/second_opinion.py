"""Advisory AI note on a candidate card. It never changes the score or the order of the list.

The model receives numbered facts from the anonymized card and the need: no name, contacts, region,
free-text summary or ids. Every point it returns must cite those facts; a point that cites nothing,
cites a missing fact, brings a number absent from its facts or touches a protected topic is dropped.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from app.services.ai import providers

MAX_FACTS = 40
MAX_POINTS = 4
MAX_QUESTIONS = 3
_TEXT_MAX = 240

_SYSTEM = (
    "Ты помогаешь рекрутеру прочитать анонимную карточку кандидата. Опирайся только на пронумерованные "
    "факты. Не ставь оценок и баллов, не советуй нанять или отказать, не сравнивай с другими людьми. "
    "Не упоминай возраст, пол, внешность, здоровье, семью, национальность, религию, город и регион. "
    "Не добавляй чисел, которых нет в фактах. Ответ только JSON без пояснений:\n"
    '{"summary": "одна-две фразы", "strengths": [{"text": "...", "facts": [1]}], '
    '"risks": [{"text": "...", "facts": [2]}], "questions": [{"text": "вопрос для интервью", "facts": [3]}]}\n'
    f"Не больше {MAX_POINTS} пунктов в strengths и risks, не больше {MAX_QUESTIONS} вопросов, "
    "каждый пункт ссылается хотя бы на один факт."
)

_PROTECTED = re.compile(
    r"возраст|молод|пожил|\bпол[ау]?\b|женщ|мужч|девушк|парен|внешн|здоров|инвалид|"
    r"беремен|декрет|семь|семейн|дет[еий]|ребён|ребен|национальн|этнич|религи|вероисп|город|регион|"
    r"переезд|прожива",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_GRADE_RU = {"intern": "стажёр", "junior": "джун", "middle": "мидл", "senior": "сеньор", "lead": "лид"}


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", str(line)).strip()


def facts(card: dict, need: dict) -> list[str]:
    """What the model may rely on. Order is stable, so the same card gives the same prompt."""
    out: list[str] = []
    wanted = ", ".join(need.get("skills") or []) or "не заданы"
    nice = ", ".join(need.get("nice_to_have") or [])
    out.append(f"Потребность: роль {need.get('role') or 'любая'}, грейд "
               f"{_GRADE_RU.get(need.get('grade') or '', 'любой')}, обязательные навыки: {wanted}"
               + (f", желательные: {nice}" if nice else ""))
    state = "подтверждён тестом" if card.get("grade_source") == "assessed" else "не подтверждён"
    out.append(f"Категория кандидата: {card.get('role') or 'не указана'}, грейд "
               f"{_GRADE_RU.get(card.get('grade') or '', 'не указан')}, грейд {state}")
    years = card.get("experience_years")
    if years is not None:
        out.append("Опыт работы: нет" if years == 0 else f"Опыт работы, лет: {years}")
    if card.get("matched_skills"):
        out.append("Есть из обязательных: " + ", ".join(card["matched_skills"]))
    if card.get("missing_skills"):
        out.append("Нет из обязательных: " + ", ".join(card["missing_skills"]))
    extra = [s for s in card.get("stack") or [] if s not in set(card.get("matched_skills") or [])][:10]
    if extra:
        out.append("Другие навыки: " + ", ".join(extra))
    for d in (card.get("disciplines") or [])[:2]:
        rank = f", разряд {d['best_rank']}" if d.get("best_rank") else ""
        out.append(f"ФСП, {d.get('label')}: событий {d.get('events_count')}{rank}")
    match = card.get("match") or {}
    for line in [*(match.get("plus") or []), *(match.get("minus") or []), *(match.get("info") or []),
                 *(card.get("why") or [])]:
        line = _clean(line)
        if line and line not in out and not _PROTECTED.search(line):
            out.append(line)
    return [_clean(f)[:_TEXT_MAX] for f in out][:MAX_FACTS]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER.findall(text)}


def _point(raw, known: list[str]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    text = _clean(raw.get("text", ""))[:_TEXT_MAX]
    cited = raw.get("facts")
    if not text or not isinstance(cited, list) or _PROTECTED.search(text):
        return None
    refs = sorted({n for n in cited if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(known)})
    if not refs or len(refs) != len(set(cited)):
        return None
    if not _numbers(text) <= set().union(*(_numbers(known[n - 1]) for n in refs)):
        return None
    return {"text": text, "facts": [known[n - 1] for n in refs]}


def parse(content: str, known: list[str]) -> tuple[dict, int]:
    """The grounded part of the model's answer and how many points were dropped."""
    match = re.search(r"\{.*\}", content or "", re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    dropped, note = 0, {}
    for key, cap in (("strengths", MAX_POINTS), ("risks", MAX_POINTS), ("questions", MAX_QUESTIONS)):
        raw = data.get(key) if isinstance(data.get(key), list) else []
        kept = [p for p in (_point(r, known) for r in raw[:cap]) if p]
        dropped += len(raw) - len(kept)
        note[key] = kept
    summary = _clean(data.get("summary", ""))[:_TEXT_MAX * 2]
    every = set().union(*(_numbers(f) for f in known)) if known else set()
    if summary and (_PROTECTED.search(summary) or not _numbers(summary) <= every):
        summary, dropped = "", dropped + 1
    note["summary"] = summary
    return note, dropped


async def second_opinion(card: dict, need: dict) -> dict:
    """Raises ProviderError when no model is connected or the call fails."""
    provider = providers.active()
    if provider is None:
        raise providers.ProviderError("ИИ-помощник не подключён")
    known = facts(card, need)
    user = "\n".join(f"{i}. {f}" for i, f in enumerate(known, 1))
    content = await providers.chat(provider, provider.model, _SYSTEM, user, temperature=0.0, limit=4000)
    note, dropped = parse(content, known)
    return {
        **note,
        "dropped": dropped,
        "facts_used": len(known),
        "advisory": True,
        "affects_score": False,
        "provider": provider.kind,
        "model": provider.model,
        "generated_at": datetime.now(UTC).isoformat(),
    }

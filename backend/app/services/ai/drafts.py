"""Item drafts from a model. A draft is never served and never enters the item bank.

The writer and the checker must be two different models. The checker sees the stem only, not the
writer's key. The draft is kept only when both name the same key, the key is not already written
in the stem, and the text has no name, email, phone or Telegram. The test itself does not call this.
An agreed draft waits in item_drafts for a person; approval does not put it into the bank.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.items import LEVEL_B
from app.items.registry import BLUEPRINTS
from app.models.item_draft import ItemDraft
from app.services.ai.assistant import has_identity

logger = logging.getLogger(__name__)

_WRITER = (
    "Составь одно учебное задание. В запросе нет резюме и нет персональных данных. "
    'Верни только JSON {"stem": "условие", "key": "короткий ответ"}. '
    "Не указывай имя, почту и телефон."
)
_CHECKER = (
    "Дан текст задания. Правильный ответ в нём не назван. "
    'Верни только JSON {"key": "короткий ответ"}.'
)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str
    served: bool = False
    stem: str = ""
    key: str = ""

    def __post_init__(self) -> None:
        if self.served:
            raise RuntimeError("a draft is never served")


def judge(stem: str, writer_key: str, checker_key: str) -> Verdict:
    """Compare two independent keys. This does not store the draft."""
    stem = stem.strip()
    left, right = writer_key.strip(), checker_key.strip()
    if not stem or has_identity(stem) or has_identity(left) or has_identity(right):
        return Verdict(False, "identity")
    if not left or left != right:
        return Verdict(False, "disagree")
    if left in stem:
        return Verdict(False, "leaked_in_stem")
    return Verdict(True, "agree")


def _object(content: str) -> dict:
    match = _OBJECT.search(content or "")
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


async def _chat(model: str, system: str, user: str) -> str:
    from gigachat import GigaChat

    giga = GigaChat(
        credentials=settings.GIGACHAT_CREDENTIALS,
        scope=settings.GIGACHAT_SCOPE,
        model=model,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        timeout=30,
    )
    try:
        resp = await giga.achat({
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user[:4000]},
            ],
            "temperature": 0.0,
        })
    finally:
        close = getattr(giga, "aclose", None)
        if close:
            await close()
    return str(resp.choices[0].message.content or "")


def ready() -> str | None:
    """None when two different models are configured, otherwise why drafts are off."""
    if not (settings.AI_ENABLED and settings.GIGACHAT_CREDENTIALS and settings.GIGACHAT_CHECK_MODEL):
        return "model_off"
    if settings.GIGACHAT_CHECK_MODEL == settings.GIGACHAT_MODEL:
        return "same_model"
    return None


async def propose(spec: str, topic: str, level: int) -> Verdict:
    """Ask for a draft. The arguments are a specialization, a topic and a level, never a résumé."""
    blocked = ready()
    if blocked:
        return Verdict(False, blocked)
    brief = f"Специализация: {spec}. Тема: {topic}. Уровень: {level}."
    try:
        written = _object(await _chat(settings.GIGACHAT_MODEL, _WRITER, brief))
        stem, key = str(written.get("stem") or ""), str(written.get("key") or "")
        if not stem or not key:
            return Verdict(False, "model_error")
        checked = _object(await _chat(settings.GIGACHAT_CHECK_MODEL, _CHECKER, stem))
    except Exception:
        logger.exception("Item draft was not accepted")
        return Verdict(False, "model_error")
    verdict = judge(stem, key, str(checked.get("key") or ""))
    return replace(verdict, stem=stem.strip(), key=key.strip()) if verdict.accepted else verdict


def brief_error(spec: str, topic: str, level: int) -> str | None:
    """The request names a specialization, a topic of its blueprint and an item level."""
    if spec not in BLUEPRINTS:
        return "Нет такой специализации"
    if topic not in BLUEPRINTS[spec]:
        return "У этой специализации нет такой темы"
    if level not in LEVEL_B:
        return "Уровень задания — от 1 до 5"
    return None


async def queue_draft(db: AsyncSession, spec: str, topic: str, level: int) -> tuple[Verdict, ItemDraft | None]:
    """Ask for a draft and keep it for a person only when both models agreed. Nothing else is stored."""
    verdict = await propose(spec, topic, level)
    if not verdict.accepted:
        return verdict, None
    row = ItemDraft(spec=spec, topic=topic, level=level, stem=verdict.stem[:4000], key=verdict.key[:200],
                    status="pending")
    db.add(row)
    await db.flush()
    return verdict, row


def review(row: ItemDraft, decision: str, note: str | None, now: datetime) -> ItemDraft:
    """Approve or reject once. An approved draft is a starting point for a family author, not a bank item."""
    if row.status != "pending":
        raise ValueError("already_reviewed")
    if decision not in ("approved", "rejected"):
        raise ValueError("bad_decision")
    if note and has_identity(note):
        raise ValueError("identity")
    row.status, row.note, row.reviewed_at = decision, (note or None), now
    return row

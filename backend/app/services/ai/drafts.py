"""Item drafts from a model. A draft is never served and never enters the item bank.

The writer and the checker must be two different models. The checker sees the stem only, not the
writer's key. The draft is kept only when both name the same key, the key is not already written
in the stem, and the text has no name, email, phone or Telegram. The test itself does not call this.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.core.config import settings
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


def _ready() -> str | None:
    if not (settings.AI_ENABLED and settings.GIGACHAT_CREDENTIALS and settings.GIGACHAT_CHECK_MODEL):
        return "model_off"
    if settings.GIGACHAT_CHECK_MODEL == settings.GIGACHAT_MODEL:
        return "same_model"
    return None


async def propose(spec: str, topic: str, level: int) -> Verdict:
    """Ask for a draft. The arguments are a specialization, a topic and a level, never a résumé."""
    blocked = _ready()
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
    return judge(stem, key, str(checked.get("key") or ""))

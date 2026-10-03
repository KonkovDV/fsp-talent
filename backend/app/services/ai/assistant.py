"""
AI assistant (advisor only). Deterministic extraction is always the baseline; an LLM may
propose extra skills, but each must normalize to the taxonomy and quote the source text
verbatim, otherwise it is dropped. The candidate confirms every skill before it is used.

GigaChat integration notes
--------------------------
* Use `async with GigaChat(...)` — it handles OAuth token refresh and connection pooling.
* `achat` accepts a `gigachat.models.Chat` model, NOT a plain dict.
* `GIGACHAT_CREDENTIALS` = client credentials (Base64-encoded client_id:client_secret)
  from https://developers.sber.ru/studio.
* Scope GIGACHAT_API_PERS = personal; GIGACHAT_API_CORP = corporate.
"""
from __future__ import annotations
import json
import logging
import re
from app.core.config import settings
from app.services.categorization import GRADES
from app.services.skills import ROLES, extract_skills, is_grounded, normalize_skill

logger = logging.getLogger(__name__)

_RESUME_PROMPT = (
    "Ты извлекаешь технические навыки из резюме. Верни только JSON-массив объектов "
    '{"skill": "название", "quote": "точная цитата из текста"}. Цитата должна дословно '
    "встречаться в тексте. Не придумывай навыков, которых нет в тексте."
)
_GRADE_WORDS = {
    "junior": ("junior", "джун", "джуниор", "стажер", "стажёр", "intern"),
    "middle": ("middle", "мидл"),
    "senior": ("senior", "сеньор", "синьор"),
    "lead": ("lead", "тимлид", "лид"),
}
_ROLE_WORDS = {
    "backend": ("backend", "бэкенд", "бекенд"),
    "frontend": ("frontend", "фронтенд"),
    "fullstack": ("fullstack", "фулстек", "full-stack"),
    "ml": ("ml-инженер", "ml engineer", "data scientist", "машинн"),
    "devops": ("devops", "девопс", "sre"),
    "security": ("безопасност", "пентест", "security", "иб"),
    "embedded": ("embedded", "встраиваем", "микроконтроллер"),
    "mobile": ("mobile", "мобильн", "ios", "android"),
}
_DISC_WORDS = {
    "algorithmic": ("алгоритм", "олимпиад"),
    "product": ("продуктов", "хакатон"),
    "security": ("ctf", "кибербез"),
    "bas": ("бас", "беспилот", "дрон"),
    "robotics": ("робот",),
}


def _word_hit(text: str, words: tuple[str, ...]) -> bool:
    """Stem-aware word match: short words require whole-word boundaries."""
    return any(
        re.search(rf"(?<!\w){re.escape(w)}" + (r"(?!\w)" if len(w) <= 4 else ""), text)
        for w in words
    )


def parse_query(q: str) -> dict:
    """Parse a free-form employer search query into structured filters."""
    low = q.lower()
    return {
        "skills": sorted({e.skill for e in extract_skills(q)}),
        "role": next((r for r in ROLES if _word_hit(low, _ROLE_WORDS[r])), None),
        "grade": next((g for g in GRADES if _word_hit(low, _GRADE_WORDS[g])), None),
        "discipline": next((d for d, w in _DISC_WORDS.items() if _word_hit(low, w)), None),
    }


async def _llm_skills(text: str) -> list[dict]:
    """Call GigaChat to extract skills from resume text.

    Uses the official gigachat SDK with:
    - `async with GigaChat(...)` for proper OAuth lifecycle management
    - `gigachat.models.Chat` + `Messages` + `MessagesRole` instead of plain dicts
    """
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole

    async with GigaChat(
        credentials=settings.GIGACHAT_CREDENTIALS,
        scope=settings.GIGACHAT_SCOPE,
        model=settings.GIGACHAT_MODEL,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        timeout=30,
    ) as giga:
        response = await giga.achat(
            Chat(
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content=_RESUME_PROMPT),
                    Messages(role=MessagesRole.USER, content=text[:8000]),
                ],
                temperature=0.1,
            )
        )

    content = response.choices[0].message.content
    match = re.search(r"\[.*\]", content, re.S)
    return json.loads(match.group(0)) if match else []


async def parse_resume(text: str) -> dict:
    """Parse a candidate resume: rule-based extraction + optional GigaChat augmentation.

    Every LLM-proposed skill must:
    1. Normalise to the canonical taxonomy.
    2. Be grounded in a verbatim quote from the source text.
    Items failing either check are silently rejected (counted in `llm_rejected`).
    The candidate must confirm each skill before it is stored.
    """
    found = {
        e.skill: {"name": e.skill, "source_quote": e.evidence, "source": "rules"}
        for e in extract_skills(text)
    }
    llm_used, rejected = False, 0

    if settings.AI_ENABLED and settings.GIGACHAT_CREDENTIALS:
        try:
            for item in await _llm_skills(text):
                name = normalize_skill(str(item.get("skill", "")))
                quote = str(item.get("quote", ""))
                if name and quote and is_grounded(quote, text):
                    found.setdefault(
                        name,
                        {"name": name, "source_quote": quote, "source": "llm"},
                    )
                else:
                    rejected += 1
            llm_used = True
        except Exception:
            logger.exception(
                "GigaChat call failed — returning rules-only result. "
                "Check GIGACHAT_CREDENTIALS and GIGACHAT_SCOPE settings."
            )

    return {
        "skills": sorted(found.values(), key=lambda s: s["name"]),
        "llm_used": llm_used,
        "llm_rejected": rejected,
        "note": "Подтвердите каждый навык перед сохранением",
    }

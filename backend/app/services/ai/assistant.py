"""AI assistant (advisor only). Deterministic extraction is always the baseline; an LLM may
propose extra skills, but each must normalize to the taxonomy and quote the source text
verbatim, otherwise it is dropped. The candidate confirms every skill before it is used.
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

# Matches a word whose final character is Cyrillic (i.e. a morphological stem).
_CYR_END = re.compile(r"[а-яёА-ЯЁ]$")


def _word_hit(text: str, words) -> bool:
    """Match any of `words` against `text` (caller should lower-case `text` first).

    * Cyrillic-ending tokens are morphological stems — only the left boundary is
      enforced, so "алгоритм" matches "алгоритмическое".
    * All other tokens (ASCII words, abbreviations) require a strict right boundary,
      so "security" does NOT match "insecurity" or "cybersecurity".
    """
    return any(
        re.search(
            rf"(?<!\w){re.escape(w)}" + ("" if _CYR_END.search(w) else r"(?!\w)"),
            text,
        )
        for w in words
    )


def parse_query(q: str) -> dict:
    low = q.lower()
    return {
        "skills": sorted({e.skill for e in extract_skills(q)}),
        "role": next((r for r in ROLES if _word_hit(low, _ROLE_WORDS[r])), None),
        "grade": next((g for g in GRADES if _word_hit(low, _GRADE_WORDS[g])), None),
        "discipline": next((d for d, w in _DISC_WORDS.items() if _word_hit(low, w)), None),
    }


async def _llm_skills(text: str) -> list[dict]:
    from gigachat import GigaChat

    giga = GigaChat(
        credentials=settings.GIGACHAT_CREDENTIALS,
        scope=settings.GIGACHAT_SCOPE,
        model=settings.GIGACHAT_MODEL,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        timeout=30,
    )
    try:
        resp = await giga.achat(
            {
                "messages": [
                    {"role": "system", "content": _RESUME_PROMPT},
                    {"role": "user", "content": text[:8000]},
                ],
                "temperature": 0.1,
            }
        )
    finally:
        close = getattr(giga, "aclose", None)
        if close:
            await close()
    content = resp.choices[0].message.content
    match = re.search(r"\[.*\]", content, re.DOTALL)
    return json.loads(match.group(0)) if match else []


async def parse_resume(text: str) -> dict:
    found = {e.skill: {"name": e.skill, "source_quote": e.evidence, "source": "rules"} for e in extract_skills(text)}
    llm_used, rejected = False, 0
    if settings.AI_ENABLED and settings.GIGACHAT_CREDENTIALS:
        try:
            for item in await _llm_skills(text):
                name, quote = normalize_skill(str(item.get("skill", ""))), str(item.get("quote", ""))
                if name and quote and is_grounded(quote, text):
                    found.setdefault(name, {"name": name, "source_quote": quote, "source": "llm"})
                else:
                    rejected += 1
            llm_used = True
        except Exception:
            logger.exception("GigaChat call failed, rules-only result returned")
    return {
        "skills": sorted(found.values(), key=lambda s: s["name"]),
        "llm_used": llm_used,
        "llm_rejected": rejected,
        "note": "Подтвердите каждый навык перед сохранением",
    }

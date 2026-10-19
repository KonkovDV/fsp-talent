"""Advisor only. Rules extract skills first. A model may propose more, but each proposal
must match the skill list and quote the resume verbatim, or it is dropped. The candidate
confirms every skill. The written answer allows cloud models, including foreign ones, and
prefers open weights. This module calls GigaChat with the name, mail and phone already
removed: the check machine has no GPU, and the test never asks a model for a grade.
"""
from __future__ import annotations

import json
import logging
import re

from app.services.categorization import GRADES
from app.services.skills import ROLES, extract_skills, is_grounded, normalize_skill, quote_names_skill
from app.services.soft_skills import ITEMS as _SOFT_SKILLS

logger = logging.getLogger(__name__)

_RESUME_PROMPT = (
    "Ты извлекаешь технические навыки из резюме. Верни только JSON-массив объектов "
    '{"skill": "название", "quote": "точная цитата из текста"}. Цитата должна дословно '
    "встречаться в тексте. Не придумывай навыков, которых нет в тексте."
)
_GRADE_WORDS = {
    "intern": ("intern", "стажер", "стажёр"),
    "junior": ("junior", "джун", "джуниор"),
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
    "embedded": ("embedded", "встраиваем", "микроконтроллер", "робототех"),
    "mobile": ("mobile", "мобильн", "ios", "android"),
    "qa": ("тестиров", "qa", "quality assurance"),
    "analyst": ("аналитик", "analyst"),
    "data": ("инженер данных", "data engineer", "дата-инжен"),
}
_DISC_WORDS = {
    "algorithmic": ("алгоритм", "олимпиад"),
    "product": ("продуктов", "хакатон"),
    "security": ("ctf", "кибербез"),
    "bas": ("бас", "беспилот", "дрон"),
    "robotics": ("робот",),
}

# Matches a word whose final character is Cyrillic (a morphological stem candidate).
_CYR_END = re.compile(r"[а-яёА-ЯЁ]$")


def _find_word(text: str, words) -> re.Match[str] | None:
    """First match of `words` in `text`. The same boundary rules as `_word_hit`."""
    for w in words:
        boundary = "" if (_CYR_END.search(w) and len(w) > 4) else r"(?!\w)"
        match = re.search(rf"(?<!\w){re.escape(w)}{boundary}", text, re.IGNORECASE)
        if match:
            return match
    return None


def _word_hit(text: str, words) -> bool:
    """Match any of `words` against `text` (caller should lower-case `text` first).

    Stem heuristic: a token is treated as a Cyrillic morphological stem—with no right
    word-boundary—only when it satisfies BOTH:
      1. ends in a Cyrillic letter (not ASCII/digit)
      2. length > 4 (rules out short abbreviations such as 'бас', 'иб', 'дрон')

    Examples:
      'алгоритм'  (8, Cyrillic) -> stem -> matches 'алгоритмическое'
      'беспилот' (8, Cyrillic) -> stem -> matches 'беспилотник'
      'робот'    (5, Cyrillic) -> stem -> matches 'роботехника'
      'бас'     (3, Cyrillic) -> boundary -> no match inside 'бассейн'
      'иб'      (2, Cyrillic) -> boundary -> no match inside 'ибраимов'
      'дрон'    (4, Cyrillic) -> boundary -> no match inside 'дрономания'
      'security'  (8, ASCII)    -> boundary -> no match inside 'cybersecurity'
    """
    return _find_word(text, words) is not None


_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+7|8)(?:[\s().\-]*\d){10}(?!\d)")
_INTL_PHONE = re.compile(r"(?<!\w)\+\d{1,3}(?:[\s().\-]*\d){8,14}(?!\d)")
_TELEGRAM = re.compile(r"(?<![\w@])@[A-Za-z][A-Za-z0-9_]{4,31}")
_URL = re.compile(r"https?://[^\s<>)\]]+", re.IGNORECASE)
_PROFILE_URL = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|t\.me|telegram\.me|linkedin\.com)/\S+",
    re.IGNORECASE,
)
_CALLED_NAME = re.compile(
    r"(?iu)\b(?:меня\s+зовут|моё\s+имя|мое\s+имя|my\s+name\s+is)\s+"
    r"([A-ZА-ЯЁ][a-zа-яё]{1,19}(?:\s+[A-ZА-ЯЁ][a-zа-яё]{1,19}){1,2})"
)
_YEARS = re.compile(
    r"(?:стаж|опыт(?:\s+работы)?)[^\d]{0,40}(\d{1,2})\s*(?:года?|лет)(?!\w)"
    r"|(\d{1,2})\s*(?:года?|лет)(?!\w)\s+(?:опыт|стаж)"
    r"|(\d{1,2})\s*\+?\s*years?(?!\w)",
    re.IGNORECASE,
)
_RELOCATE_NO = re.compile(
    r"не\s+готов[а-яё]*\s+к\s+(?:переезду|релокац\w*)|not\s+(?:ready|willing)\s+to\s+relocate",
    re.IGNORECASE,
)
_RELOCATE_YES = re.compile(
    r"(?<!не\s)готов[а-яё]*\s+к\s+(?:переезду|релокац\w*)|(?:ready|willing)\s+to\s+relocate",
    re.IGNORECASE,
)
_NAME_LINE = re.compile(r"[A-Za-zА-Яа-яЁё\-]+(?:\s+[A-Za-zА-Яа-яЁё\-]+){1,2}")
_NAME_WORD = re.compile(r"^(?:[A-ZА-ЯЁ][a-zа-яё]{1,19}|[A-ZА-ЯЁ]{2,20})$")
_NAME_STOP = {
    "резюме", "resume", "опыт", "навыки", "образование", "контакты", "проекты", "работа",
    "developer", "engineer", "разработчик", "инженер", "программист", "специалист",
    "python", "java", "javascript", "backend", "frontend", "fullstack", "devops", "mobile",
    "senior", "junior", "middle", "lead", "intern", "москва", "петербург", "санкт", "россия",
}


def _quoted(text: str, match: re.Match[str]) -> dict:
    """The value's evidence is the line that contains the match, so the quote is verbatim."""
    left = text.rfind("\n", 0, match.start()) + 1
    right = text.find("\n", match.end())
    line = text[left:right if right >= 0 else len(text)].strip()
    return {"value": match.group(0), "quote": line}


def _earliest(text: str, groups: dict[str, tuple[str, ...]]) -> dict | None:
    best: tuple[int, str, re.Match[str]] | None = None
    for key, words in groups.items():
        match = _find_word(text, words)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), key, match)
    if best is None:
        return None
    _, key, match = best
    left = text.rfind("\n", 0, match.start()) + 1
    right = text.find("\n", match.end())
    line = text[left:right if right >= 0 else len(text)].strip()
    return {"value": key, "quote": line}


def _full_name(text: str) -> dict | None:
    """A short line of two or three capitalized words near the top. Job titles are rejected."""
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()][:8]:
        if "@" in line or any(ch.isdigit() for ch in line) or not _NAME_LINE.fullmatch(line):
            continue
        words = [part for word in line.split() for part in word.split("-")]
        if any(word.lower() in _NAME_STOP for word in words) or not all(_NAME_WORD.match(word) for word in words):
            continue
        return {"value": line, "quote": line}
    return None


def _phone(text: str) -> dict | None:
    match = _PHONE.search(text)
    if match is None:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) != 11:
        return None
    normalized = "+7" + digits[1:]
    hit = _quoted(text, match)
    hit["value"] = normalized
    return hit


def _relocation(text: str) -> dict | None:
    """Explicit relocation line only. A refusal wins over a positive match on the same text."""
    refusal = _RELOCATE_NO.search(text)
    if refusal is not None:
        hit = _quoted(text, refusal)
        hit["value"] = False
        return hit
    ready = _RELOCATE_YES.search(text)
    if ready is not None:
        hit = _quoted(text, ready)
        hit["value"] = True
        return hit
    return None


def extract_resume_fields(text: str) -> dict:
    """Name, contacts, years, grade and role. Each value keeps a verbatim quote; nothing is guessed.

    The login email is returned for display and is not a profile field: the account address stays the
    confirmed one. Soft skills are quoted too and stay out of the skill taxonomy.
    """
    email = _EMAIL.search(text)
    telegram = _TELEGRAM.search(text)
    years = _YEARS.search(text)
    year_value = next((int(g) for g in years.groups() if g), None) if years else None
    if year_value is not None and not 0 <= year_value <= 50:
        year_value = None
    soft = []
    for name, words in _SOFT_SKILLS:
        match = _find_word(text, words)
        if match:
            left = text.rfind("\n", 0, match.start()) + 1
            right = text.find("\n", match.end())
            soft.append({"name": name, "quote": text[left:right if right >= 0 else len(text)].strip()})
    return {
        "full_name": _full_name(text),
        "email": _quoted(text, email) if email else None,
        "phone": _phone(text),
        "telegram": _quoted(text, telegram) if telegram else None,
        "experience_years": None if year_value is None or years is None else {
            "value": year_value, "quote": _quoted(text, years)["quote"]},
        "grade": _earliest(text, _GRADE_WORDS),
        "role": _earliest(text, _ROLE_WORDS),
        "relocation": _relocation(text),
        "soft_skills": soft,
    }


def has_identity(text: str) -> bool:
    """True when the text carries an email, a phone, Telegram or a personal name."""
    return bool(
        _EMAIL.search(text) or _PHONE.search(text) or _INTL_PHONE.search(text)
        or _TELEGRAM.search(text) or _PROFILE_URL.search(text) or _full_name(text)
        or _CALLED_NAME.search(text)
    )


def for_model(text: str) -> str:
    """Strip the patterns we know how to find before a cloud model sees the text.

    This is not a guarantee that a free-text resume contains no name or contact. A short capitalized
    line, a Russian phone, an email, Telegram, an international number, a URL and «меня зовут …»
    are replaced. Anything else can remain, and the product must not promise a clean document.
    The candidate still sees the original fields: they are extracted from the source and confirmed by hand.
    """
    redacted = _EMAIL.sub("[email]", text)
    redacted = _PHONE.sub("[phone]", redacted)
    redacted = _INTL_PHONE.sub("[phone]", redacted)
    redacted = _TELEGRAM.sub("[telegram]", redacted)
    redacted = _URL.sub("[url]", redacted)
    name = _full_name(text)
    if name:
        redacted = redacted.replace(name["value"], "[name]")
    for match in _CALLED_NAME.finditer(text):
        redacted = redacted.replace(match.group(1), "[name]")
    return redacted


def parse_query(q: str) -> dict:
    low = q.lower()
    return {
        "skills": sorted({e.skill for e in extract_skills(q)}),
        "role": next((r for r in ROLES if _word_hit(low, _ROLE_WORDS[r])), None),
        "grade": next((g for g in GRADES if _word_hit(low, _GRADE_WORDS[g])), None),
        "discipline": next((d for d, w in _DISC_WORDS.items() if _word_hit(low, w)), None),
    }


async def _llm_skills(text: str) -> list[dict]:
    from app.services.ai import providers

    provider = providers.active()
    if provider is None:
        return []
    content = await providers.chat(provider, provider.model, _RESUME_PROMPT, text, temperature=0.1)
    match = re.search(r"\[.*\]", content, re.DOTALL)
    return json.loads(match.group(0)) if match else []


async def parse_resume(text: str, allow_llm: bool = True) -> dict:
    from app.services.ai import providers

    sent = for_model(text)
    found = {e.skill: {"name": e.skill, "source_quote": e.evidence, "source": "rules"} for e in extract_skills(text)}
    llm_used, rejected = False, 0
    if allow_llm and providers.active() is not None:
        try:
            for item in await _llm_skills(sent):
                name, quote = normalize_skill(str(item.get("skill", ""))), str(item.get("quote", ""))
                # The quote must be in the resume and must name this skill: otherwise the pair would
                # be signed into resume_token and raise the skill to "resume quote" trust.
                if name and quote and is_grounded(quote, text) and quote_names_skill(name, quote):
                    found.setdefault(name, {"name": name, "source_quote": quote, "source": "llm"})
                else:
                    rejected += 1
            llm_used = True
        except Exception:
            logger.exception("Model call failed, rules-only result returned")
    return {
        "skills": sorted(found.values(), key=lambda s: s["name"]),
        "llm_used": llm_used,
        "llm_rejected": rejected,
        "note": "Проверьте навыки и нажмите «Применить» у полей, которые хотите перенести в профиль",
        "model_text": sent,
        **extract_resume_fields(text),
    }

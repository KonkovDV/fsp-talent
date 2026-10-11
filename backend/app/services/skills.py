"""
Skill taxonomy, alias normalization and deterministic, evidence-backed extraction.

Every extracted skill carries the exact substring of the source text it came from,
so any extraction (rule-based or LLM) can be verified mechanically.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from app.core.config import settings

# canonical -> (roles, aliases); aliases are matched case-insensitively on word boundaries
TAXONOMY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Python": (("backend", "ml", "qa", "analyst", "data"), ("python", "питон", "пайтон")),
    "Go": (("backend",), ("golang", "голанг", "go", "гоу")),
    "Java": (("backend",), ("java", "джава", "жава")),
    "Kotlin": (("backend", "mobile"), ("kotlin", "котлин")),
    "C#": (("backend",), ("c#", ".net", "dotnet", "asp.net")),
    "PHP": (("backend",), ("php", "пхп")),
    "Rust": (("backend", "embedded"), ("rust", "раст")),
    "Node.js": (("backend", "fullstack"), ("node.js", "nodejs", "node", "нода")),
    "FastAPI": (("backend",), ("fastapi", "фастапи")),
    "Django": (("backend",), ("django", "джанго")),
    "Flask": (("backend",), ("flask", "фласк")),
    "Spring": (("backend",), ("spring", "spring boot", "спринг")),
    "SQL": (("backend", "ml", "analyst", "data"), ("sql",)),
    "PostgreSQL": (("backend", "data"), ("postgresql", "postgres", "постгрес", "постгре", "постгрескл")),
    "MySQL": (("backend",), ("mysql", "майскл")),
    "MongoDB": (("backend",), ("mongodb", "mongo", "монго", "монгодб")),
    "Redis": (("backend",), ("redis", "редис")),
    "ClickHouse": (("backend", "ml"), ("clickhouse", "кликхаус")),
    "Kafka": (("backend", "data"), ("kafka", "кафка")),
    "RabbitMQ": (("backend",), ("rabbitmq", "рэббит")),
    "gRPC": (("backend",), ("grpc",)),
    "JavaScript": (("frontend", "fullstack"), ("javascript", "js", "джаваскрипт", "жаваскрипт")),
    "TypeScript": (("frontend", "fullstack"), ("typescript", "ts", "тайпскрипт")),
    "React": (("frontend", "fullstack"), ("react", "react.js", "reactjs", "реакт")),
    "Vue.js": (("frontend",), ("vue", "vue.js", "vue3", "vuejs", "вью")),
    "Angular": (("frontend",), ("angular", "ангуляр")),
    "Next.js": (("frontend", "fullstack"), ("next.js", "nextjs")),
    "HTML/CSS": (("frontend",), ("html", "css", "html5", "css3")),
    "Tailwind CSS": (("frontend",), ("tailwind", "tailwindcss")),
    "PyTorch": (("ml",), ("pytorch", "torch", "пайторч")),
    "TensorFlow": (("ml",), ("tensorflow", "keras", "тензорфлоу")),
    "scikit-learn": (("ml",), ("scikit-learn", "sklearn", "сайкит")),
    "Pandas": (("ml", "analyst", "data"), ("pandas", "пандас")),
    "NumPy": (("ml",), ("numpy", "нампи", "нампай")),
    "NLP": (("ml",), ("nlp", "обработка естественного языка")),
    "Computer Vision": (("ml", "embedded"), ("computer vision", "компьютерное зрение", "opencv")),
    "LLM": (("ml",), ("llm", "rag", "языковые модели")),
    "Machine Learning": (("ml",), ("machine learning", "машинное обучение", "ml")),
    "Docker": (("devops", "backend"), ("docker", "докер")),
    "Kubernetes": (("devops",), ("kubernetes", "k8s", "кубер", "кубернетес")),
    "Terraform": (("devops",), ("terraform", "терраформ")),
    "Ansible": (("devops",), ("ansible", "ансибл")),
    "CI/CD": (("devops",), ("ci/cd", "gitlab ci", "github actions", "jenkins")),
    "Linux": (("devops", "security", "embedded"), ("linux", "линукс", "bash")),
    "Nginx": (("devops",), ("nginx", "нгинкс")),
    "Networking": (("devops", "security", "embedded"), ("networking", "сети tcp/ip", "tcp/ip", "ip-адресация")),
    "Prometheus/Grafana": (("devops",), ("prometheus", "grafana")),
    "Pentesting": (("security",), ("pentest", "pentesting", "пентест", "тестирование на проникновение")),
    "CTF": (("security",), ("ctf",)),
    "Reverse Engineering": (("security",), ("reverse engineering", "реверс", "ida pro", "ghidra")),
    "Cryptography": (("security",), ("cryptography", "криптография")),
    "Web Security": (("security",), ("owasp", "web security", "burp", "burp suite", "xss", "sql injection")),
    "Forensics": (("security",), ("forensics", "форензика")),
    "OSINT": (("security",), ("osint",)),
    "C": (("embedded",), ("ansi c", "язык c", "язык си")),
    "C++": (("embedded", "backend"), ("c++", "cpp", "плюсы")),
    "STM32": (("embedded",), ("stm32",)),
    "Arduino": (("embedded",), ("arduino", "ардуино")),
    "ROS": (("embedded",), ("ros", "ros2")),
    "RTOS": (("embedded",), ("rtos", "freertos")),
    "PX4/ArduPilot": (("embedded",), ("px4", "ardupilot", "mavlink")),
    "Swift": (("mobile",), ("swift", "свифт")),
    "Flutter": (("mobile",), ("flutter", "dart", "флаттер")),
    "Android": (("mobile",), ("android", "андроид")),
    "Algorithms": (("backend", "ml"), ("алгоритмы", "algorithms", "структуры данных", "data structures")),
    "pytest": (("qa",), ("pytest", "пайтест")),
    "Playwright": (("qa",), ("playwright", "плейрайт")),
    "Selenium": (("qa",), ("selenium", "селениум")),
    "A/B-тесты": (("analyst",), ("a/b-тесты", "a/b тесты", "аб-тесты")),
    "Airflow": (("data",), ("airflow", "эйрфлоу")),
    "Spark": (("data",), ("spark", "apache spark", "спарк")),
}

ROLES = ("backend", "frontend", "fullstack", "ml", "devops", "security", "embedded", "mobile", "qa", "analyst", "data")

# Cyrillic letters that look like Latin ones; folded only when the whole token becomes ASCII
_LOOKALIKES = str.maketrans("сореахкмтвнСОРЕАХКМТВН", "copeaxkmtbhCOPEAXKMTBH")
_BOUNDARY_L = r"(?<![\w+#.])"
_BOUNDARY_R = r"(?![\w+#])"


def _fold(token: str) -> str:
    folded = token.translate(_LOOKALIKES)
    return folded if folded.isascii() else token


@lru_cache
def _alias_index() -> dict[str, str]:
    """Aliases only. A canonical name is not an alias: bare "c" must not be extracted from prose."""
    index: dict[str, str] = {}
    for canonical, (_, aliases) in TAXONOMY.items():
        for alias in aliases:
            index[alias.lower()] = canonical
    return index


def normalize_skill(raw: str) -> str | None:
    """Return the canonical skill name, or None if the skill is not in the taxonomy."""
    key = _fold(" ".join(raw.strip().split())).lower()
    if key in _alias_index():
        return _alias_index()[key]
    for canonical in TAXONOMY:
        if canonical.lower() == key:
            return canonical
    return None


def roles_for(skill: str) -> tuple[str, ...]:
    entry = TAXONOMY.get(skill)
    return entry[0] if entry else ()


@dataclass(frozen=True)
class ExtractedSkill:
    skill: str
    evidence: str
    start: int
    end: int


@lru_cache
def _patterns() -> list[tuple[re.Pattern, str, bool]]:
    pats = []
    for alias, canonical in sorted(_alias_index().items(), key=lambda kv: -len(kv[0])):
        pats.append((re.compile(_BOUNDARY_L + re.escape(alias) + _BOUNDARY_R, re.IGNORECASE), canonical,
                     alias.isascii()))
    return pats


# Negation (NegEx, Chapman et al. 2001, doi:10.1006/jbin.2001.1029): a trigger shortly before a skill, inside
# the same clause, means the text says the person does NOT have it: «не работал с Kubernetes», «без Docker»,
# «нет опыта с Kafka», «хочу изучить Go», «no experience with Rust».
_NEG_TRIGGER = re.compile(
    r"(?<!\w)(?:не|нет|без|хочу\s+изучить|планирую|no|not|never|without)(?!\w)", re.IGNORECASE)
# Pseudo-negations: «не только Python», «не менее 3 лет с Java» do not deny the skill.
_NEG_PSEUDO = re.compile(r"(?:не|not)\s+(?:только|менее|меньше|ниже|хуже|позднее|позже|only)(?!\w)", re.IGNORECASE)
# A clause ends at sentence punctuation, a comma, a bracket or a contrastive conjunction.
_CLAUSE_END = re.compile(r"[.;:!?,()\[\]\n•|]|(?<!\w)(?:но|а|однако|зато|but|however)(?!\w)", re.IGNORECASE)
_NEG_WINDOW_WORDS = 3
_WORD = re.compile(r"\w+")


def is_negated(text: str, start: int) -> bool:
    """A negation trigger stands at most three words before `start`, in the same clause."""
    left = text[max(0, start - 120):start]
    ends = list(_CLAUSE_END.finditer(left))
    if ends:
        left = left[ends[-1].end():]
    for trigger in _NEG_TRIGGER.finditer(left):
        if _NEG_PSEUDO.match(left, trigger.start()):
            continue
        if len(_WORD.findall(left[trigger.end():])) <= _NEG_WINDOW_WORDS:
            return True
    return False


def extract_skills(text: str) -> list[ExtractedSkill]:
    """Rule-based extraction. Folding is 1:1 per character, so offsets stay valid for the original text.

    A negated mention («не работал с Kubernetes») is skipped; a later plain mention of the same skill still counts.
    """
    folded = text.translate(_LOOKALIKES)
    found: dict[str, ExtractedSkill] = {}
    taken: list[tuple[int, int]] = []
    for pattern, canonical, ascii_alias in _patterns():
        if canonical in found:
            continue
        for haystack in ((text, folded) if ascii_alias else (text,)):
            m = next((m for m in pattern.finditer(haystack) if not is_negated(text, m.start())), None)
            if m and not any(s < m.end() and m.start() < e for s, e in taken):
                found[canonical] = ExtractedSkill(canonical, text[m.start():m.end()], m.start(), m.end())
                taken.append((m.start(), m.end()))
                break
    return sorted(found.values(), key=lambda s: s.start)


TRUST_WEIGHT = {"test_confirmed": 1.0, "resume_confirmed": 0.75, "self_reported": 0.55}

TRUST_RU = {
    "test_confirmed": "подтверждён тестом",
    "resume_confirmed": "цитата из резюме",
    "self_reported": "заявлен",
}


@dataclass
class SkillDraft:
    name: str
    raw_name: str | None
    source_quote: str | None
    trust_level: str
    confirmed: bool
    created_at: datetime | None
    confirmed_at: datetime | None


def sign_resume_evidence(participant_id: str, pairs: list[tuple[str, str]]) -> str:
    """A quote raises a skill's weight only when this server extracted it from a resume."""
    items = sorted({(name, quote) for name, quote in pairs if name and quote})[:40]
    payload = json.dumps(
        {"sub": participant_id, "items": [{"n": name, "q": quote} for name, quote in items]},
        ensure_ascii=False, separators=(",", ":"),
    ).encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=") + "." + sig


def read_resume_evidence(token: str, participant_id: str) -> set[tuple[str, str]]:
    """Pairs this token proves for this account. A forged or foreign token proves nothing."""
    try:
        raw, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        expected = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return set()
        data = json.loads(payload)
        if data.get("sub") != participant_id:
            return set()
        found = set()
        for item in data.get("items") or []:
            name, quote = item.get("n"), item.get("q")
            if isinstance(name, str) and isinstance(quote, str) and name and quote:
                found.add((name, quote))
        return found
    except (ValueError, json.JSONDecodeError, TypeError, AttributeError):
        return set()


def with_resume_token(participant_id: str, parsed: dict) -> dict:
    pairs = [
        (item.get("name") or "", (item.get("source_quote") or "").strip())
        for item in parsed.get("skills") or []
    ]
    # Defence in depth (N-3): only a quote that names its skill is signed as resume evidence.
    pairs = [(name, quote) for name, quote in pairs if name and quote and quote_names_skill(name, quote)]
    return {**parsed, "resume_token": sign_resume_evidence(participant_id, pairs) if pairs else None}


def plan_skill_replacement(existing: list[SkillDraft], incoming: list[tuple[str, str, str | None]],
                           now: datetime, allowed: set[tuple[str, str]] | None = None) -> list[SkillDraft]:
    """Rebuild a skill list without throwing away evidence or accepting a quote the client invented.

    A skill the test confirmed stays confirmed. A resume quote counts only when this server
    extracted it (``allowed``) or the profile already stored that same quote. Saving again
    does not move the date.
    """
    allowed = allowed or set()
    by_name = {row.name: row for row in existing}
    tested = {name: row for name, row in by_name.items() if row.trust_level == "test_confirmed"}
    seen: set[str] = set()
    out: list[SkillDraft] = []
    for name, raw, quote in incoming:
        if not name or name in seen:
            continue
        seen.add(name)
        old = by_name.get(name)
        created = old.created_at if old and old.created_at else now
        if name in tested:
            src = tested[name]
            out.append(SkillDraft(name, src.raw_name or raw, src.source_quote, "test_confirmed", True,
                                  src.created_at or now, src.confirmed_at or now))
            continue
        proven = bool(quote) and (name, quote) in allowed
        same = bool(old and old.trust_level == "resume_confirmed" and old.source_quote
                    and quote == old.source_quote)
        if proven or same:
            src_quote = quote if proven else old.source_quote
            confirmed_at = old.confirmed_at if same and old and old.confirmed_at else now
            out.append(SkillDraft(name, raw, src_quote, "resume_confirmed", True, created, confirmed_at))
            continue
        out.append(SkillDraft(name, raw, None, "self_reported", True, created, None))
    return out


def skill_line(name: str, trust_level: str) -> str:
    return f"{name} ({TRUST_RU.get(trust_level, TRUST_RU['self_reported'])})"


# A model quote longer than this is not a quote of one skill; it is a paragraph that happens to contain it.
MAX_QUOTE_CHARS = 200


def quote_names_skill(skill: str, quote: str) -> bool:
    """The quote itself names this skill (an alias from the taxonomy, word-bounded).

    Audit 2026-10 (second opinion, N-3; OWASP LLM01/LLM05): a substring check alone let a model, or a
    prompt injection inside the resume, pin "Kubernetes" to the quote "опыт". The pair (skill, quote) is
    accepted only when the deterministic extractor finds that very skill inside the quote.
    """
    if not quote or len(quote) > MAX_QUOTE_CHARS:
        return False
    return any(found.skill == skill for found in extract_skills(quote))


def is_grounded(evidence: str, text: str) -> bool:
    """An extracted skill is accepted only if its evidence is an exact (whitespace-normalized) substring."""
    ev = " ".join(evidence.split()).lower()
    return bool(ev) and ev in " ".join(text.split()).lower()

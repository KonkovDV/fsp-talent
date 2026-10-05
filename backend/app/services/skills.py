"""
Skill taxonomy, alias normalization and deterministic, evidence-backed extraction.

Every extracted skill carries the exact substring of the source text it came from,
so any extraction (rule-based or LLM) can be verified mechanically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# canonical -> (roles, aliases); aliases are matched case-insensitively on word boundaries
TAXONOMY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Python": (("backend", "ml"), ("python", "питон", "пайтон")),
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
    "SQL": (("backend", "ml"), ("sql",)),
    "PostgreSQL": (("backend",), ("postgresql", "postgres", "постгрес", "постгре", "постгрескл")),
    "MySQL": (("backend",), ("mysql", "майскл")),
    "MongoDB": (("backend",), ("mongodb", "mongo", "монго", "монгодб")),
    "Redis": (("backend",), ("redis", "редис")),
    "ClickHouse": (("backend", "ml"), ("clickhouse", "кликхаус")),
    "Kafka": (("backend",), ("kafka", "кафка")),
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
    "Pandas": (("ml",), ("pandas", "пандас")),
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
}

ROLES = ("backend", "frontend", "fullstack", "ml", "devops", "security", "embedded", "mobile")

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


def extract_skills(text: str) -> list[ExtractedSkill]:
    """Rule-based extraction. Folding is 1:1 per character, so offsets stay valid for the original text."""
    folded = text.translate(_LOOKALIKES)
    found: dict[str, ExtractedSkill] = {}
    taken: list[tuple[int, int]] = []
    for pattern, canonical, ascii_alias in _patterns():
        if canonical in found:
            continue
        for haystack in ((text, folded) if ascii_alias else (text,)):
            m = pattern.search(haystack)
            if m and not any(s < m.end() and m.start() < e for s, e in taken):
                found[canonical] = ExtractedSkill(canonical, text[m.start():m.end()], m.start(), m.end())
                taken.append((m.start(), m.end()))
                break
    return sorted(found.values(), key=lambda s: s.start)


def is_grounded(evidence: str, text: str) -> bool:
    """An extracted skill is accepted only if its evidence is an exact (whitespace-normalized) substring."""
    ev = " ".join(evidence.split()).lower()
    return bool(ev) and ev in " ".join(text.split()).lower()

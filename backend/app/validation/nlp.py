"""Field-level accuracy of resume and vacancy parsing: `python -m app.validation.nlp [--resumes 60] [--seed 2026]`.

Both parts run the production rules only. No LLM is called: a model needs a key and does not repeat itself.

Resumes. A generator draws a persona with a known answer (name, email, phone, Telegram, years in the trade,
specialization, grade, skills) and writes it out in three layouts of our own: a profile card with labelled
lines, a cover letter in plain sentences and a sectioned CV with capitalised block titles. Each layout is
drawn into a PDF and read back through the product path `extract_pdf_text` → `extract_resume_fields` and
`extract_skills`. Every field is compared with the answer the generator kept.

Vacancies. Hand-written texts with a gold card (`resources/nlp_vacancies_gold.json`) go through `draft_need`.
Specialization, grade, salary range, work format and city are scalar checks; required, optional and all
skills are set checks.

Scalar fields score exact equality: a miss is an error, and a gold null is right only when nothing is found.
Sets score precision, recall and F1 per document, then the mean over documents (CoNLL-2003, arXiv:cs/0306050).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.services.ai.assistant import extract_resume_fields
from app.services.need_draft import draft_need
from app.services.pdf_profile import _font, extract_pdf_text
from app.services.skills import extract_skills

RESOURCES = Path(__file__).resolve().parent / "resources"
LAYOUTS = ("card", "letter", "blocks")
RESUME_FIELDS = ("full_name", "email", "phone", "telegram", "experience_years", "role", "grade")


# ---------------------------------------------------------------- set metric --------------------------------------

def _share(part: int, whole: int) -> float:
    """part / whole; an empty whole has nothing to get wrong and scores 1."""
    return part / whole if whole else 1.0


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    """Precision, recall and F1 of a predicted set against the gold set, rounded to 3 digits.

    An empty prediction scores precision 1, an empty gold set scores recall 1; F1 is their harmonic mean.
    """
    overlap = len(pred.intersection(gold))
    precision, recall = _share(overlap, len(pred)), _share(overlap, len(gold))
    total = precision + recall
    f1 = 0.0 if total == 0 else 2 * precision * recall / total
    return tuple(round(x, 3) for x in (precision, recall, f1))


def mean_prf(scores: list[tuple[float, float, float]]) -> dict[str, float]:
    """Mean P, R and F1 over documents; no documents gives None for all three."""
    if not scores:
        return {"p": None, "r": None, "f1": None}
    columns = list(zip(*scores, strict=True))
    return {name: round(statistics.fmean(col), 3) for name, col in zip(("p", "r", "f1"), columns, strict=True)}


# ---------------------------------------------------------------- personas -----------------------------------------

MEN = ("Григорий", "Тимур", "Роман", "Олег", "Степан", "Виталий", "Глеб", "Арсений", "Лев", "Фёдор", "Ярослав")
WOMEN = ("Екатерина", "Софья", "Наталья", "Ольга", "Вера", "Таисия", "Злата", "Ульяна", "Регина")
# Surnames in the masculine form; the feminine one adds «а» (all of these end in a consonant).
SURNAMES = ("Белов", "Громов", "Жуков", "Зайцев", "Комаров", "Ларионов", "Медведев", "Носов", "Орлов",
            "Рябов", "Тихонов", "Филатов", "Щербаков", "Юдин", "Яковлев", "Гусев", "Данилов")
FATHERS = ("Романов", "Олегов", "Тимуров", "Степанов", "Глебов", "Львов")  # + «ич» / «на»
LATIN = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                 ("a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "j", "k", "l", "m", "n", "o", "p", "r", "s",
                  "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"), strict=True))
MAIL_HOSTS = ("yandex.ru", "ya.ru", "mail.ru", "bk.ru", "gmail.com", "proton.me")
OPERATORS = ("901", "915", "921", "950", "967", "985", "996")
TOWNS = ("Казань", "Самара", "Томск", "Иркутск", "Воронеж", "Калининград", "Тюмень")

# Specialization → (titles people put on top, skill pool by canonical taxonomy name).
TRACKS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "backend": (("Backend-инженер", "Бэкенд-разработчик (Python)", "Backend developer"),
                ("Python", "Go", "Java", "PostgreSQL", "Redis", "Kafka", "gRPC", "Docker", "FastAPI", "RabbitMQ")),
    "frontend": (("Frontend-инженер", "Фронтенд-разработчик", "Frontend developer (React)"),
                 ("TypeScript", "JavaScript", "React", "Angular", "Next.js", "Tailwind CSS", "HTML/CSS")),
    "fullstack": (("Fullstack-разработчик", "Full-stack инженер"),
                  ("TypeScript", "Node.js", "React", "PostgreSQL", "Docker", "Next.js")),
    "ml": (("ML-инженер", "Data Scientist", "ML engineer (NLP)"),
           ("Python", "PyTorch", "TensorFlow", "Pandas", "NumPy", "NLP", "LLM", "ClickHouse")),
    "devops": (("DevOps-инженер", "SRE-инженер", "Инженер DevOps / SRE"),
               ("Kubernetes", "Terraform", "Ansible", "Prometheus/Grafana", "Linux", "Nginx", "CI/CD")),
    "qa": (("Инженер по тестированию", "QA-инженер (автотесты)"),
           ("pytest", "Playwright", "Selenium", "Python", "SQL", "CI/CD")),
    "mobile": (("Мобильный разработчик", "iOS-разработчик", "Android-разработчик"),
               ("Kotlin", "Swift", "Flutter", "Android")),
    "security": (("Специалист по информационной безопасности", "Инженер по безопасности приложений"),
                 ("Pentesting", "Web Security", "Reverse Engineering", "Cryptography", "Forensics", "OSINT")),
    "analyst": (("Продуктовый аналитик", "Аналитик данных"),
                ("SQL", "Python", "Pandas", "A/B-тесты", "ClickHouse")),
    "data": (("Инженер данных", "Data engineer"),
             ("Airflow", "Spark", "Kafka", "PostgreSQL", "SQL", "ClickHouse")),
}
# How the grade is written next to the title; one spelling per grade is picked at random.
GRADE_SPELLING = {"intern": ("стажёр", "Intern"), "junior": ("Junior", "джуниор"), "middle": ("Middle", "мидл"),
                  "senior": ("Senior", "сеньор"), "lead": ("Lead", "тимлид")}
# Grade weights of the generator (none = the title carries no grade) and years in the trade per grade.
GRADE_WEIGHTS = (("intern", 6), ("junior", 24), ("middle", 32), ("senior", 20), ("lead", 6), (None, 12))
YEARS = {"intern": (1, 1), "junior": (1, 3), "middle": (3, 6), "senior": (6, 12), "lead": (8, 15), None: (2, 9)}
# Everyday spellings the taxonomy should still map to the canonical name.
SLANG = {"PostgreSQL": "постгрес", "Kubernetes": "кубер", "TypeScript": "TS", "Python": "питон",
         "JavaScript": "JS", "Go": "golang", "PyTorch": "torch", "CI/CD": "GitHub Actions", "Flutter": "dart"}
EMPLOYERS = ("«Вектор Телеком»", "«Меридиан Финанс»", "«Кедр Лабс»", "«Облачные решения»", "«Позитрон»",
             "«Горизонт Ритейл»")
PROJECTS = ("перевёл сервис расчётов на очереди и убрал ночные простои",
            "собрал внутреннюю платформу отчётов для трёх отделов",
            "сократил время сборки с сорока до двенадцати минут",
            "запустил мобильное приложение для курьеров",
            "настроил мониторинг и дежурства для команды из восьми человек")


@dataclass
class Persona:
    full_name: str
    email: str
    phone: str            # canonical +7XXXXXXXXXX, what the parser must return
    phone_text: str       # as written in the resume
    telegram: str | None
    experience_years: int
    role: str
    grade: str | None
    skills: set[str]
    skill_text: list[str] = field(default_factory=list)
    title: str = ""
    town: str = ""
    employer: str = ""
    project: str = ""


def _latin(word: str) -> str:
    return "".join(LATIN.get(ch, ch) for ch in word.lower())


def _phone_pair(rng: random.Random) -> tuple[str, str]:
    op = rng.choice(OPERATORS)
    num = f"{rng.randrange(10_000_000):07d}"
    written = rng.choice((f"+7 {op} {num[:3]}-{num[3:5]}-{num[5:]}", f"8 ({op}) {num}",
                          f"+7-{op}-{num[:3]}-{num[3:5]}-{num[5:]}", f"8{op}{num}"))
    return f"+7{op}{num}", written


def _weighted(rng: random.Random, pairs):
    values, weights = zip(*pairs, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def make_persona(rng: random.Random, idx: int) -> Persona:
    woman = rng.random() < 0.4
    given = rng.choice(WOMEN if woman else MEN)
    family = rng.choice(SURNAMES) + ("а" if woman else "")
    order = rng.random()
    if order < 0.3:
        full_name = f"{family} {given} {rng.choice(FATHERS)}{'на' if woman else 'ич'}"
    elif order < 0.75:
        full_name = f"{given} {family}"
    else:
        full_name = f"{family} {given}"
    handle = f"{_latin(given)[0]}{_latin(family)}{idx}"
    canonical, written = _phone_pair(rng)
    role = rng.choice(sorted(TRACKS))
    titles, pool = TRACKS[role]
    grade = _weighted(rng, GRADE_WEIGHTS)
    low, high = YEARS[grade]
    skills = sorted(rng.sample(pool, k=min(len(pool), rng.randint(4, 7))))
    skill_text = [SLANG[s] if s in SLANG and rng.random() < 0.3 else s for s in skills]
    return Persona(
        full_name=full_name, email=f"{handle}@{rng.choice(MAIL_HOSTS)}", phone=canonical, phone_text=written,
        telegram=f"@{handle}_dev" if rng.random() < 0.65 else None, experience_years=rng.randint(low, high),
        role=role, grade=grade, skills=set(skills), skill_text=skill_text, title=rng.choice(titles),
        town=rng.choice(TOWNS), employer=rng.choice(EMPLOYERS), project=rng.choice(PROJECTS),
    )


def _plural_years(n: int) -> str:
    tens, ones = n % 100, n % 10
    if 11 <= tens <= 14 or ones == 0 or ones >= 5:
        return "лет"
    return "год" if ones == 1 else "года"


def _grade_word(p: Persona, rng: random.Random) -> str:
    return rng.choice(GRADE_SPELLING[p.grade]) if p.grade else ""


# ---------------------------------------------------------------- layouts ------------------------------------------
# Each layout returns lines of (style, text); style is "h" for a heading and "t" for body text.

def layout_card(p: Persona, rng: random.Random) -> list[tuple[str, str]]:
    """A profile card: the name, then «Label: value» lines and a skills line separated by semicolons."""
    grade = _grade_word(p, rng)
    lines = [("h", p.full_name), ("t", p.title + (f" · {grade}" if grade else "")),
             ("t", f"Город: {p.town}"), ("t", f"E-mail: {p.email}"), ("t", f"Тел.: {p.phone_text}")]
    if p.telegram:
        lines.append(("t", f"Telegram: {p.telegram}"))
    lines += [("t", f"Стаж в IT: {p.experience_years} {_plural_years(p.experience_years)}"),
              ("t", f"Место работы: {p.employer}"),
              ("t", "Ключевые навыки: " + "; ".join(p.skill_text)),
              ("t", f"Достижение: {p.project}.")]
    return lines


def layout_letter(p: Persona, rng: random.Random) -> list[tuple[str, str]]:
    """A cover letter. Some contacts and the experience come in forms the rules do not read, on purpose."""
    grade = _grade_word(p, rng)
    years = p.experience_years
    if rng.random() < 0.2:
        exp = f"пишу код за деньги с {2026 - years} года"            # start year: not parsed, a known gap
    else:
        exp = f"мой опыт в коммерческой разработке — {years} {_plural_years(years)}"
    tg = p.telegram
    if tg and rng.random() < 0.2:
        tg = f"https://t.me/{tg[1:]}"                                # a link instead of @handle: a known gap
    reach = f"Почта {p.email}, телефон {p.phone_text}" + (f", Telegram {tg}" if tg else "") + "."
    level = f" уровня {grade}" if grade else ""
    return [("h", p.full_name), ("t", f"{p.title}{level}"), ("t", ""),
            ("t", f"Здравствуйте! Откликаюсь на вашу вакансию: {exp}."),
            ("t", f"Сейчас работаю в компании {p.employer}, где {p.project}."),
            ("t", "Каждый день работаю с " + ", ".join(p.skill_text) + "."),
            ("t", reach), ("t", f"Живу в городе {p.town}, готов к удалённой работе.")]


def layout_blocks(p: Persona, rng: random.Random) -> list[tuple[str, str]]:
    """A sectioned CV: capitalised block titles, bullets under each."""
    grade = _grade_word(p, rng)
    contacts = [("t", f"• {p.email}"), ("t", f"• {p.phone_text}")]
    if p.telegram:
        contacts.append(("t", f"• {p.telegram}"))
    years = p.experience_years
    return [("h", p.full_name), ("t", (f"{grade} " if grade else "") + p.title),
            ("h", "КОНТАКТЫ"), *contacts,
            ("h", "КАРЬЕРА"), ("t", f"• Общий стаж {years} {_plural_years(years)}"),
            ("t", f"• {p.employer}: {p.project}"),
            ("h", "СТЕК"), *[("t", f"• {s}") for s in p.skill_text]]


RENDERERS = {"card": layout_card, "letter": layout_letter, "blocks": layout_blocks}


def render_pdf(lines: list[tuple[str, str]]) -> bytes:
    from fpdf import FPDF

    font = _font()
    if font is None:
        raise SystemExit("Нужен шрифт с кириллицей (DejaVu Sans)")
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    pdf.add_font("Body", "", str(font))
    for style, text in lines:
        pdf.set_font("Body", size=13 if style == "h" else 10)
        pdf.multi_cell(0, 8 if style == "h" else 6, text or " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


# ---------------------------------------------------------------- resume check -------------------------------------

def _found(fields: dict, name: str):
    item = fields.get(name)
    return item["value"] if item else None


def check_resume(p: Persona, layout: str, rng: random.Random) -> tuple[dict[str, bool], tuple[float, float, float]]:
    text = extract_pdf_text(render_pdf(RENDERERS[layout](p, rng)))
    fields = extract_resume_fields(text)
    truth = {"full_name": p.full_name, "email": p.email, "phone": p.phone, "telegram": p.telegram,
             "experience_years": p.experience_years, "role": p.role, "grade": p.grade}
    right = {name: _found(fields, name) == truth[name] for name in RESUME_FIELDS}
    return right, prf({hit.skill for hit in extract_skills(text)}, p.skills)


def resume_eval(n: int, seed: int) -> dict:
    """Accuracy per field and mean skill P/R/F1, per layout. The same personas go through every layout."""
    people = [make_persona(random.Random(f"{seed}:{i}"), i) for i in range(n)]
    report = {}
    for layout in LAYOUTS:
        rng = random.Random(f"{seed}:{layout}")
        tally = dict.fromkeys(RESUME_FIELDS, 0)
        sets = []
        for p in people:
            right, skill_score = check_resume(p, layout, rng)
            for name, ok in right.items():
                tally[name] += ok
            sets.append(skill_score)
        report[layout] = {"n": n, **{k: round(v / n, 3) for k, v in tally.items()},
                          **{f"skills_{k}": v for k, v in mean_prf(sets).items()}}
    return report


# ---------------------------------------------------------------- vacancy check ------------------------------------

VACANCY_FIELDS = ("role", "grade", "salary", "work_format", "city")


def _scalars(draft: dict, gold: dict) -> dict[str, tuple]:
    """(found, gold) per scalar field; the salary is one field with both bounds."""
    return {
        "role": (draft["role"], gold["role"]), "grade": (draft["grade"], gold["grade"]),
        "salary": ((draft["salary_from"], draft["salary_to"]), (gold["salary_from"], gold["salary_to"])),
        "work_format": (draft["work_format"], gold["work_format"]), "city": (draft["city"], gold["city"]),
    }


def _skill_groups(draft: dict, gold: dict) -> dict[str, tuple[set, set]]:
    required, optional = set(gold.get("skills") or ()), set(gold.get("nice") or ())
    found_req, found_opt = set(draft.get("skills") or ()), set(draft.get("nice_to_have") or ())
    return {"required": (found_req, required), "optional": (found_opt, optional),
            "union": (found_req | found_opt, required | optional)}


def vacancy_eval(name: str = "nlp_vacancies_gold.json") -> dict:
    """Scalar accuracy and skill-set P/R/F1 on a gold file. «optional» averages only texts that list such skills."""
    items = json.loads((RESOURCES / name).read_text(encoding="utf-8"))
    tally = dict.fromkeys(VACANCY_FIELDS, 0)
    groups: dict[str, list] = {"required": [], "optional": [], "union": []}
    misses = []
    for item in items:
        draft, gold = draft_need(item["text"]), item["gold"]
        wrong = [k for k, (got, want) in _scalars(draft, gold).items() if got != want]
        for k in VACANCY_FIELDS:
            tally[k] += k not in wrong
        for group, (found, want) in _skill_groups(draft, gold).items():
            if group != "optional" or want:
                groups[group].append(prf(found, want))
        if wrong:
            misses.append({"head": item["text"].strip().splitlines()[0], "fields": wrong})
    n = len(items)
    return {"n": n, **{k: round(v / n, 3) for k, v in tally.items()},
            "skills": {group: mean_prf(scores) for group, scores in groups.items()}, "misses": misses}


# ---------------------------------------------------------------- CLI ----------------------------------------------

def _print(report: dict, per_layout: int) -> None:
    print(f"Резюме: {per_layout} персон × {len(LAYOUTS)} шаблона, зерно {report['seed']}; "
          "PDF → extract_pdf_text → extract_resume_fields / extract_skills")
    print(f"{'поле':<18}" + "".join(f"{name:>10}" for name in LAYOUTS))
    for name in (*RESUME_FIELDS, "skills_p", "skills_r", "skills_f1"):
        print(f"{name:<18}" + "".join(f"{report['resumes'][lay][name]:>10.3f}" for lay in LAYOUTS))
    v = report["vacancies"]
    print(f"\nВакансии: {v['n']} текстов, draft_need")
    for k in VACANCY_FIELDS:
        print(f"{k:<18}{v[k]:>8.3f}")
    for group, s in v["skills"].items():
        print(f"skills {group:<11} P {s['p']:.3f}  R {s['r']:.3f}  F1 {s['f1']:.3f}")
    for miss in v["misses"]:
        print(f"  мимо: {miss['head'][:50]} → {', '.join(miss['fields'])}")


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resumes", type=int, default=60, help="персон; каждая проходит все шаблоны")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    started = time.perf_counter()
    report = {"seed": args.seed, "resumes": resume_eval(args.resumes, args.seed)}
    report["vacancies"] = vacancy_eval()
    report["seconds"] = round(time.perf_counter() - started, 1)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print(report, args.resumes)
        print(f"\nВремя: {report['seconds']} с")
    return report


if __name__ == "__main__":
    main()

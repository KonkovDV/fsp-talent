"""Field-level accuracy of resume and vacancy parsing: `python -m app.validation.nlp [--resumes 60] [--seed 2026]`.

Two parts, both rule-based and deterministic (no LLM: the model needs a key and is not reproducible):

1. Resumes. Synthetic people with a known truth (name, email, phone, Telegram, years of experience, role, grade,
   skills) are rendered to PDF in two layouts: a two-column export in the style of hh.ru (labels on the left,
   content on the right) and a free-form text resume. The PDF goes through the production path
   `extract_pdf_text` → `extract_resume_fields` + `extract_skills`; each field is compared with the truth.
2. Vacancies. 24 hand-written vacancy texts of different styles (`resources/nlp_vacancies_gold.json`) go through
   `draft_need`; role, grade, required and nice-to-have skills, salary range, work format and city are compared.

Scalar fields: exact match (a missing value counts as an error; a gold `null` is right only if nothing is found).
Skill sets: precision, recall and F1 averaged over documents (CoNLL-2003 style, arXiv:cs/0306050).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from app.services.ai.assistant import extract_resume_fields
from app.services.need_draft import draft_need
from app.services.pdf_profile import _font, extract_pdf_text
from app.services.skills import extract_skills

RESOURCES = Path(__file__).resolve().parent / "resources"

SURNAMES = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков",
            "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов"]
FIRST = ["Алексей", "Дмитрий", "Иван", "Максим", "Артём", "Никита", "Егор", "Кирилл", "Михаил", "Андрей"]
FIRST_F = ["Анна", "Мария", "Елена", "Дарья", "Полина", "Ксения", "Виктория", "Алина"]
PATRON = ["Сергеевич", "Андреевич", "Игоревич", "Олегович", "Викторович"]
PATRON_F = ["Сергеевна", "Андреевна", "Игоревна", "Олеговна"]
TRANSLIT = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
                          "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
                          "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh",
                          "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"})

# role → (headline variants, skill pool); headlines are how people title resumes, not our keyword list
ROLES = {
    "backend": (["Python-разработчик (backend)", "Backend-разработчик", "Бэкенд-разработчик на Go"],
                ["Python", "Go", "Java", "FastAPI", "Django", "PostgreSQL", "Redis", "Kafka", "Docker", "SQL"]),
    "frontend": (["Frontend-разработчик", "Фронтенд-разработчик (React)"],
                 ["JavaScript", "TypeScript", "React", "Vue.js", "HTML/CSS", "Next.js"]),
    "ml": (["ML-инженер", "Data Scientist"],
           ["Python", "PyTorch", "scikit-learn", "Pandas", "NumPy", "NLP", "SQL"]),
    "devops": (["DevOps-инженер", "SRE / DevOps"],
               ["Linux", "Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Nginx"]),
    "qa": (["Инженер по тестированию", "QA Automation Engineer"],
           ["Python", "pytest", "Playwright", "Selenium", "SQL", "CI/CD"]),
    "mobile": (["Android-разработчик", "Мобильный разработчик (iOS)"], ["Kotlin", "Android", "Swift", "Flutter"]),
    "security": (["Специалист по информационной безопасности", "Пентестер"],
                 ["Pentesting", "Web Security", "Linux", "CTF", "OSINT", "Networking"]),
}
GRADE_WORDS = {"intern": "Стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior", "lead": "Тимлид"}
# common spellings people use; the parser is expected to map them to the canonical skill
ALIASES = {"PostgreSQL": "Postgres", "Kubernetes": "k8s", "JavaScript": "JS", "scikit-learn": "sklearn",
           "Go": "Golang", "CI/CD": "GitLab CI", "Vue.js": "Vue"}
COMPANIES = ["ООО «Северный код»", "АО «Т-Платформы»", "ООО «Логос Софт»", "ПАО «Связьинвест»", "ООО «Нейролаб»"]
ABOUT = ["Люблю разбираться в сложных системах и доводить задачи до релиза.",
         "Участвовал в хакатонах, веду небольшой технический блог.",
         "Ответственный, быстро обучаюсь, работаю в команде.",
         "Интересуюсь архитектурой и производительностью."]


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


def _phone(rng: random.Random) -> tuple[str, str]:
    d = [rng.randint(0, 9) for _ in range(7)]
    code = rng.choice(["912", "903", "916", "977", "999"])
    tail = "".join(map(str, d))
    shown = rng.choice([f"+7 ({code}) {tail[:3]}-{tail[3:5]}-{tail[5:]}", f"8 {code} {tail[:3]} {tail[3:5]} {tail[5:]}",
                        f"+7{code}{tail}"])
    return shown, f"+7{code}{tail}"


def person(rng: random.Random, idx: int) -> dict:
    female = rng.random() < 0.35
    surname = rng.choice(SURNAMES) + ("а" if female else "")
    first = rng.choice(FIRST_F if female else FIRST)
    style = rng.random()
    if style < 0.4:
        name = f"{surname} {first} {rng.choice(PATRON_F if female else PATRON)}"
    elif style < 0.8:
        name = f"{surname} {first}"
    else:
        name = f"{first} {surname}"
    login = f"{first.lower().translate(TRANSLIT)}.{surname.lower().translate(TRANSLIT)}{idx}"
    phone_shown, phone = _phone(rng)
    role = rng.choice(sorted(ROLES))
    headlines, pool = ROLES[role]
    grade = rng.choice(["junior", "middle", "senior", None]) if rng.random() < 0.9 else "lead"
    years = {"junior": rng.randint(1, 2), "middle": rng.randint(2, 5), "senior": rng.randint(5, 10),
             "lead": rng.randint(7, 12), None: rng.randint(1, 8)}[grade]
    skills = sorted(rng.sample(pool, k=min(len(pool), rng.randint(3, 6))))
    return {
        "full_name": name, "email": f"{login}@{rng.choice(['mail.ru', 'yandex.ru', 'gmail.com'])}",
        "phone": phone, "phone_shown": phone_shown,
        "telegram": f"@{login.replace('.', '_')}" if rng.random() < 0.7 else None,
        "experience_years": years, "role": role, "grade": grade, "headline": rng.choice(headlines),
        "skills": set(skills),
        "skill_words": [ALIASES[s] if s in ALIASES and rng.random() < 0.4 else s for s in skills],
        "company": rng.choice(COMPANIES), "about": rng.choice(ABOUT),
    }


def _years_ru(n: int) -> str:
    return "год" if n % 10 == 1 and n % 100 != 11 else ("года" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14)
                                                       else "лет")


def lines_hh(p: dict, rng: random.Random) -> list[tuple[str, str]]:
    """Two columns: (label, value). The label is drawn on the left, the value on the right, like an hh.ru export."""
    title = p["headline"] + (f", {GRADE_WORDS[p['grade']]}" if p["grade"] else "")
    years = p["experience_years"]
    rows = [("", p["full_name"]), ("", f"{rng.choice(['Мужчина', 'Женщина'])}, {rng.randint(21, 40)} лет"),
            ("Телефон", f"{p['phone_shown']} — предпочитаемый способ связи"), ("Почта", p["email"])]
    if p["telegram"]:
        rows.append(("Telegram", p["telegram"]))
    rows += [("", "Желаемая должность и зарплата"), ("", title),
             ("", f"Опыт работы — {years} {_years_ru(years)} {rng.randint(0, 11)} мес."),
             ("2021 — н. в.", p["company"]), ("", p["about"]),
             ("Навыки", "  ".join(p["skill_words"])), ("", "Образование: высшее, Томский политехнический университет")]
    return rows


def lines_free(p: dict, rng: random.Random) -> list[tuple[str, str]]:
    grade = f"Уровень: {GRADE_WORDS[p['grade']]}" if p["grade"] else ""
    # realistic variation the rules do not cover: a t.me link instead of @login, the start year instead of years
    tg = p["telegram"]
    if tg and rng.random() < 0.25:
        tg = "t.me/" + tg[1:]
    contacts = f"{p['email']}, {p['phone_shown']}" + (f", tg {tg}" if tg else "")
    years = p["experience_years"]
    exp = (f"В разработке с {2026 - years} года" if rng.random() < 0.25
           else f"Коммерческий опыт {years} {_years_ru(years)}")
    rows = ["РЕЗЮМЕ", p["full_name"], p["headline"], grade, contacts, "",
            f"{exp}, последнее место — {p['company']}.", f"О себе: {p['about']}",
            "Технологии: " + ", ".join(p["skill_words"]) + "."]
    return [("", r) for r in rows if r is not None]


def render_pdf(rows: list[tuple[str, str]], two_columns: bool) -> bytes:
    from fpdf import FPDF

    font = _font()
    if font is None:
        raise SystemExit("Нужен шрифт с кириллицей (DejaVu Sans)")
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Body", "", str(font))
    for label, value in rows:
        if two_columns:
            pdf.set_font("Body", size=8)
            pdf.set_x(10)
            pdf.cell(35, 7, label)
            pdf.set_font("Body", size=10)
            pdf.multi_cell(0, 7, value or " ", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Body", size=11)
            pdf.multi_cell(0, 7, value or " ", new_x="LMARGIN", new_y="NEXT")
    out = pdf.output()
    return bytes(out)


def _val(field: dict | None):
    return field["value"] if field else None


def resume_eval(n: int, seed: int) -> dict:
    rng = random.Random(seed)
    per_layout: dict[str, dict] = {}
    for layout in ("hh", "free"):
        hits = {k: 0 for k in ("full_name", "email", "phone", "telegram", "experience_years", "role", "grade")}
        skills = []
        for i in range(n):
            p = person(rng, i)
            rows = lines_hh(p, rng) if layout == "hh" else lines_free(p, rng)
            text = extract_pdf_text(render_pdf(rows, layout == "hh"))
            got = extract_resume_fields(text)
            hits["full_name"] += _val(got["full_name"]) == p["full_name"]
            hits["email"] += _val(got["email"]) == p["email"]
            hits["phone"] += _val(got["phone"]) == p["phone"]
            hits["telegram"] += _val(got["telegram"]) == p["telegram"]
            hits["experience_years"] += _val(got["experience_years"]) == p["experience_years"]
            hits["role"] += _val(got["role"]) == p["role"]
            hits["grade"] += _val(got["grade"]) == p["grade"]
            skills.append(prf({e.skill for e in extract_skills(text)}, p["skills"]))
        per_layout[layout] = {"n": n, **{k: round(v / n, 3) for k, v in hits.items()}, **_mean_prf(skills)}
    return per_layout


def _mean_prf(scores: list[tuple[float, float, float]]) -> dict:
    return {"skills_p": round(statistics.fmean(s[0] for s in scores), 3),
            "skills_r": round(statistics.fmean(s[1] for s in scores), 3),
            "skills_f1": round(statistics.fmean(s[2] for s in scores), 3)}


def vacancy_eval() -> dict:
    items = json.loads((RESOURCES / "nlp_vacancies_gold.json").read_text(encoding="utf-8"))
    keys = ("role", "grade", "salary", "work_format", "city")
    hits = {k: 0 for k in keys}
    req, nice, all_sk, errors = [], [], [], []
    for it in items:
        g, d = it["gold"], draft_need(it["text"])
        ok = {"role": d["role"] == g["role"], "grade": d["grade"] == g["grade"],
              "salary": (d["salary_from"], d["salary_to"]) == (g["salary_from"], g["salary_to"]),
              "work_format": d["work_format"] == g["work_format"], "city": d["city"] == g["city"]}
        for k in keys:
            hits[k] += ok[k]
        req.append(prf(set(d["skills"]), set(g["skills"])))
        if g["nice"]:
            nice.append(prf(set(d["nice_to_have"]), set(g["nice"])))
        all_sk.append(prf(set(d["skills"]) | set(d["nice_to_have"]), set(g["skills"]) | set(g["nice"])))
        bad = [k for k in keys if not ok[k]]
        if bad:
            errors.append({"title": it["text"].splitlines()[0], "fields": bad})
    n = len(items)
    return {"n": n, **{k: round(v / n, 3) for k, v in hits.items()},
            "required": _mean_prf(req), "nice": _mean_prf(nice), "all_skills": _mean_prf(all_sk), "errors": errors}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resumes", type=int, default=60, help="резюме на каждый шаблон")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    report = {"seed": args.seed, "resumes": resume_eval(args.resumes, args.seed), "vacancies": vacancy_eval()}
    report["seconds"] = round(time.perf_counter() - t0, 1)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report
    print(f"Резюме: {args.resumes} на шаблон, зерно {args.seed}; PDF → extract_pdf_text → extract_resume_fields")
    fields = ("full_name", "email", "phone", "telegram", "experience_years", "role", "grade",
              "skills_p", "skills_r", "skills_f1")
    print(f"{'поле':<18}{'hh (2 колонки)':>16}{'свободный':>12}")
    for f in fields:
        print(f"{f:<18}{report['resumes']['hh'][f]:>16.3f}{report['resumes']['free'][f]:>12.3f}")
    v = report["vacancies"]
    print(f"\nВакансии: {v['n']} текстов вручную, draft_need")
    for k in ("role", "grade", "salary", "work_format", "city"):
        print(f"{k:<18}{v[k]:>8.3f}")
    for name in ("required", "nice", "all_skills"):
        s = v[name]
        print(f"{name:<18} P {s['skills_p']:.3f}  R {s['skills_r']:.3f}  F1 {s['skills_f1']:.3f}")
    for e in v["errors"]:
        print(f"  ошибка: {e['title'][:50]} → {', '.join(e['fields'])}")
    print(f"\nВремя: {report['seconds']} с")
    return report


if __name__ == "__main__":
    main()

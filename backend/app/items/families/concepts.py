"""Concept items: a finite pool, so they are capped at 30 % of a session and tracked one by one for leaks."""
from __future__ import annotations

import random

from app.items import Family, Item, options_with
from app.seed.questions import QUESTIONS

GRADE_LEVEL = {"junior": 2, "middle": 3, "senior": 4, "lead": 5}
ALL_SPECS = frozenset({"backend", "frontend", "fullstack", "ml", "devops", "security", "embedded", "mobile"})


def _bank(spec: str, level: int) -> list[tuple[int, dict]]:
    return [(i, q) for i, q in enumerate(QUESTIONS)
            if q["discipline"] == spec and GRADE_LEVEL[q["target_grade"]] == level and q.get("correct_option")]


def bank_generate(rng: random.Random, level: int, spec: str) -> Item:
    pool = _bank(spec, level)
    if not pool:
        raise LookupError(f"no concept items for {spec} level {level}")
    index, q = rng.choice(pool)
    right = next(o["text"] for o in q["options"] if o["id"] == q["correct_option"])
    wrong = [o["text"] for o in q["options"] if o["id"] != q["correct_option"]]
    options, correct = options_with(rng, right, wrong)
    return Item(stem=q["question_text"], options=options, correct=correct,
                explanation="Вопрос на понимание; разбор доступен после теста.", static_key=f"bank:{index}")


# HTTP semantics: (level, situation, right status, distractors)
HTTP = [
    (1, "Ресурс по запрошенному адресу не существует.",
     "404 Not Found", ["400 Bad Request", "410 Gone", "500 Internal Server Error"]),
    (1, "POST успешно создал новый объект.",
     "201 Created", ["200 OK", "202 Accepted", "204 No Content"]),
    (2, "Запрос без токена к закрытому методу.",
     "401 Unauthorized", ["403 Forbidden", "400 Bad Request", "407 Proxy Authentication Required"]),
    (2, "Токен валиден, но у пользователя нет прав на действие.",
     "403 Forbidden", ["401 Unauthorized", "404 Not Found", "405 Method Not Allowed"]),
    (3, "Регистрация с email, который уже занят.",
     "409 Conflict", ["400 Bad Request", "422 Unprocessable Content", "403 Forbidden"]),
    (3, "JSON корректен синтаксически, но поле salary_from больше salary_to.",
     "422 Unprocessable Content", ["400 Bad Request", "409 Conflict", "412 Precondition Failed"]),
    (3, "Клиент превысил лимит запросов.",
     "429 Too Many Requests", ["503 Service Unavailable", "403 Forbidden", "409 Conflict"]),
    (4, "PUT с заголовком If-Match, но ETag ресурса уже изменился.",
     "412 Precondition Failed", ["409 Conflict", "428 Precondition Required", "304 Not Modified"]),
    (4, "Задача принята в очередь, результат будет позже.",
     "202 Accepted", ["201 Created", "200 OK", "204 No Content"]),
    (5, "Сервер требует условный запрос (If-Match), чтобы избежать потерянного обновления, а клиент его не прислал.",
     "428 Precondition Required", ["412 Precondition Failed", "409 Conflict", "400 Bad Request"]),
    (5, "GET с заголовком If-None-Match, ETag совпал.",
     "304 Not Modified", ["412 Precondition Failed", "200 OK", "204 No Content"]),
]


def http_generate(rng: random.Random, level: int, spec: str) -> Item:
    pool = [(i, row) for i, row in enumerate(HTTP) if row[0] == level]
    index, (_, situation, right, wrong) = rng.choice(pool)
    options, correct = options_with(rng, right, wrong)
    return Item(stem=f"Какой код ответа HTTP подходит лучше всего?\n{situation}", options=options, correct=correct,
                explanation=f"Правильный ответ: {right}.", static_key=f"http:{index}")


BANK = Family(
    id="concept_bank", title="Понимание: вопросы по специализации", topic="concept", kind="concept",
    specs=ALL_SPECS, skills=(), generate=bank_generate, a=1.0, supports=lambda spec, level: bool(_bank(spec, level)),
)
HTTP_FAMILY = Family(
    id="concept_http", title="Понимание: семантика HTTP", topic="concept", kind="concept",
    specs=frozenset({"backend", "frontend", "fullstack", "mobile", "devops", "security"}), skills=(),
    generate=http_generate, a=1.0,
)

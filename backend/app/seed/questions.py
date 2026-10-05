"""
Seed the test question bank with IRT-calibrated MCQ questions.

Run once: python -m app.seed.questions

30 questions across 8 disciplines x 4 grades.
Difficulty is pre-calibrated on the Rasch scale:
  -1.0 = very easy (90%+ correct at target grade)
   0.0 = medium (50% correct at target grade)
  +1.5 = hard (30% correct at target grade)
"""
from __future__ import annotations

import asyncio
import random
import uuid
from typing import Any

QUESTIONS: list[dict[str, Any]] = [
    # ===== BACKEND =====
    {"discipline": "backend", "target_grade": "junior", "difficulty": -1.0,
     "question_text": "Что возвращает `len([1, 2, 3])` в Python?",
     "options": [{"id": "a", "text": "2"}, {"id": "b", "text": "3"},
                 {"id": "c", "text": "4"}, {"id": "d", "text": "0"}],
     "correct_option": "b"},
    {"discipline": "backend", "target_grade": "junior", "difficulty": -0.5,
     "question_text": "Что такое SQL-инъекция и как от неё защититься?",
     "options": [
         {"id": "a", "text": "Атака через URL; защита — HTTPS"},
         {"id": "b", "text": "Вставка SQL через ввод; защита — параметризованные запросы"},
         {"id": "c", "text": "Переполнение буфера; защита — длина строки"},
         {"id": "d", "text": "DDoS; защита — CDN"}],
     "correct_option": "b"},
    {"discipline": "backend", "target_grade": "middle", "difficulty": 0.4,
     "question_text": "Что такое N+1 проблема в ORM и как её решить?",
     "options": [
         {"id": "a", "text": "Запрос N раз; решение — кэш Redis"},
         {"id": "b", "text": "1 запрос + N дополнительных; решение — eager loading / joinedload"},
         {"id": "c", "text": "Индекс из N+1 столбцов"},
         {"id": "d", "text": "Транзакция с N+1 операциями"}],
     "correct_option": "b"},
    {"discipline": "backend", "target_grade": "senior", "difficulty": 1.0,
     "question_text": "Как реализовать идемпотентный POST-эндпоинт (создание платежа) в распределённой системе?",
     "options": [
         {"id": "a", "text": "UUID в теле запроса как idempotency key с TTL"},
         {"id": "b", "text": "Проверка дубликатов по полям запроса с блокировкой"},
         {"id": "c", "text": "SERIALIZABLE изоляция"},
         {"id": "d", "text": "409 на любой повторный запрос"}],
     "correct_option": "a"},
    {"discipline": "backend", "target_grade": "lead", "difficulty": 1.8,
     "question_text": "CAP vs PACELC: в чём отличие?",
     "options": [
         {"id": "a", "text": "CAP: CP vs AP при разделении; PACELC добавляет L vs C при нормальной работе"},
         {"id": "b", "text": "PACELC — переименованная CAP"},
         {"id": "c", "text": "CAP для SQL, PACELC для NoSQL"},
         {"id": "d", "text": "PACELC — теорема безопасности паролей"}],
     "correct_option": "a"},
    # ===== FRONTEND =====
    {"discipline": "frontend", "target_grade": "junior", "difficulty": -0.6,
     "question_text": "Какой хук React для побочных эффектов?",
     "options": [{"id": "a", "text": "useState"}, {"id": "b", "text": "useEffect"},
                 {"id": "c", "text": "useRef"}, {"id": "d", "text": "useMemo"}],
     "correct_option": "b"},
    {"discipline": "frontend", "target_grade": "middle", "difficulty": 0.3,
     "question_text": "Чем отличается useMemo от useCallback?",
     "options": [
         {"id": "a", "text": "useMemo мемоизирует значение, useCallback — функцию"},
         {"id": "b", "text": "useMemo для асинхронных, useCallback для синхронных"},
         {"id": "c", "text": "Взаимозаменяемы"},
         {"id": "d", "text": "useMemo только для объектов"}],
     "correct_option": "a"},
    {"discipline": "frontend", "target_grade": "senior", "difficulty": 1.0,
     "question_text": "React Concurrent Mode: как работает и отличие от синхронного рендеринга?",
     "options": [
         {"id": "a", "text": "Переносит рендеринг в Web Worker"},
         {"id": "b", "text": "Рендеринг может прерываться; React откладывает низкоприоритетные обновления"},
         {"id": "c", "text": "Переименованный StrictMode"},
         {"id": "d", "text": "Только для server components"}],
     "correct_option": "b"},
    # ===== ML =====
    {"discipline": "ml", "target_grade": "junior", "difficulty": -0.9,
     "question_text": "Что такое переобучение (overfitting) и как с ним бороться?",
     "options": [
         {"id": "a", "text": "Модель плохо на train; решение — больше признаков"},
         {"id": "b", "text": "Хорошо на train, плохо на test; решение — regularization, dropout, больше данных"},
         {"id": "c", "text": "Градиент 0; решение — batch norm"},
         {"id": "d", "text": "Модель не сходится; решение — уменьшить lr"}],
     "correct_option": "b"},
    {"discipline": "ml", "target_grade": "senior", "difficulty": 1.1,
     "question_text": "Формула механизма внимания (attention) в Transformer?",
     "options": [
         {"id": "a", "text": "Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) * V"},
         {"id": "b", "text": "Attention = sigmoid(QK^T) * V"},
         {"id": "c", "text": "Attention = Q * V^T / K"},
         {"id": "d", "text": "Attention = ReLU(QKV) * d_k"}],
     "correct_option": "a"},
    # ===== DEVOPS =====
    {"discipline": "devops", "target_grade": "junior", "difficulty": -0.8,
     "question_text": "Зачем нужен .dockerignore?",
     "options": [
         {"id": "a", "text": "Исключить Docker из системы безопасности"},
         {"id": "b", "text": "Исключить файлы из build context, уменьшив размер образа и время сборки"},
         {"id": "c", "text": "Блокировать сетевые соединения"},
         {"id": "d", "text": "Указать базовый образ"}],
     "correct_option": "b"},
    {"discipline": "devops", "target_grade": "middle", "difficulty": 0.3,
     "question_text": "liveness probe vs readiness probe в Kubernetes: в чём разница?",
     "options": [
         {"id": "a", "text": "Liveness: pod жив (иначе restart); Readiness: pod готов принимать трафик"},
         {"id": "b", "text": "Одинаковы"},
         {"id": "c", "text": "Liveness для БД, readiness для аппа"},
         {"id": "d", "text": "Readiness проверяется реже, liveness чаще"}],
     "correct_option": "a"},
    {"discipline": "devops", "target_grade": "senior", "difficulty": 1.0,
     "question_text": "Zero-downtime deployment для stateful-аппа с PostgreSQL?",
     "options": [
         {"id": "a", "text": "Blue-green + backward-compatible миграции (расширяй, не сжимай)"},
         {"id": "b", "text": "Остановить БД, миграция, запустить"},
         {"id": "c", "text": "Rolling update без миграций"},
         {"id": "d", "text": "Canary без миграций"}],
     "correct_option": "a"},
    # ===== SECURITY =====
    {"discipline": "security", "target_grade": "junior", "difficulty": -0.7,
     "question_text": "Что такое XSS-атака?",
     "options": [
         {"id": "a", "text": "Кража куки через сторонний сайт"},
         {"id": "b", "text": "Инъекция вредоносного JS в страницу, выполняемого в браузере жертвы"},
         {"id": "c", "text": "Перехват HTTPS трафика"},
         {"id": "d", "text": "SQL-инъекция через заголовки"}],
     "correct_option": "b"},
    {"discipline": "security", "target_grade": "senior", "difficulty": 1.2,
     "question_text": "Как корректно хранить пароли пользователей в 2026 году?",
     "options": [
         {"id": "a", "text": "bcrypt (cost>=12), scrypt или Argon2id + соль"},
         {"id": "b", "text": "SHA-256 + соль"},
         {"id": "c", "text": "AES-256 шифрование"},
         {"id": "d", "text": "MD5 + соль"}],
     "correct_option": "a"},
    # ===== EMBEDDED =====
    {"discipline": "embedded", "target_grade": "junior", "difficulty": -0.8,
     "question_text": "Что такое UART?",
     "options": [
         {"id": "a", "text": "Беспроводный протокол"},
         {"id": "b", "text": "Последовательный интерфейс TX/RX между устройствами"},
         {"id": "c", "text": "Аналоговый фильтр"},
         {"id": "d", "text": "Протокол управления двигателем"}],
     "correct_option": "b"},
    {"discipline": "embedded", "target_grade": "middle", "difficulty": 0.4,
     "question_text": "Что такое volatile в C и зачем он нужен в embedded?",
     "options": [
         {"id": "a", "text": "Делает переменную доступной из других файлов"},
         {"id": "b", "text": "Запрещает компилятору кэшировать; нужен для регистров периферии и ISR/main shared vars"},
         {"id": "c", "text": "Защищает от переполнения"},
         {"id": "d", "text": "Инициализирует нулём"}],
     "correct_option": "b"},
    # ===== MOBILE =====
    {"discipline": "mobile", "target_grade": "junior", "difficulty": -0.7,
     "question_text": "Что такое Activity в Android?",
     "options": [
         {"id": "a", "text": "Фоновый сервис"},
         {"id": "b", "text": "Компонент, представляющий один экран с UI"},
         {"id": "c", "text": "Поток выполнения"},
         {"id": "d", "text": "Файл манифеста"}],
     "correct_option": "b"},
    {"discipline": "mobile", "target_grade": "senior", "difficulty": 1.0,
     "question_text": "Как реализовать offline-first архитектуру в мобильном приложении?",
     "options": [
         {"id": "a", "text": (
             "Local DB (Room/SQLite) как источник правды, синхронизация через "
             "conflict resolution (временные метки/CRDT)"
         )},
         {"id": "b", "text": "Кэширование HTTP через OkHttp cache"},
         {"id": "c", "text": "Хранение данных в SharedPreferences"},
         {"id": "d", "text": "Только онлайн; отключать функции offline"}],
     "correct_option": "a"},
    # ===== FULLSTACK =====
    {"discipline": "fullstack", "target_grade": "junior", "difficulty": -0.7,
     "question_text": "Что такое REST и REST API?",
     "options": [
         {"id": "a", "text": "Протокол передачи файлов"},
         {"id": "b", "text": "Архитектурный стиль API, использующий HTTP-методы и URI-ресурсы"},
         {"id": "c", "text": "Объектно-ориентированный язык программирования"},
         {"id": "d", "text": "База данных для REST-сервисов"}],
     "correct_option": "b"},
    {"discipline": "fullstack", "target_grade": "middle", "difficulty": 0.5,
     "question_text": "Что такое CORS и как его настроить правильно?",
     "options": [
         {"id": "a", "text": (
             "Механизм браузера, ограничивающий cross-origin запросы; "
             "настройка через Access-Control-Allow-Origin"
         )},
         {"id": "b", "text": "Файерволл для HTTP"},
         {"id": "c", "text": "Сертификат для защиты данных"},
         {"id": "d", "text": "CDN протокол"}],
     "correct_option": "a"},
    {"discipline": "fullstack", "target_grade": "senior", "difficulty": 1.1,
     "question_text": "WebSockets vs SSE vs Long Polling: когда что выбирать?",
     "options": [
         {"id": "a", "text": (
             "WS: full-duplex реалтайм; SSE: server-push и простой HTTP; "
             "Long Polling: поддержка прокси"
         )},
         {"id": "b", "text": "WS всегда лучше; остальные устарели"},
         {"id": "c", "text": "SSE для мобильных, WS для десктопа"},
         {"id": "d", "text": "Long Polling является стандартом 2026 года"}],
     "correct_option": "a"},
]


def balanced(question: dict[str, Any], slot: int) -> dict[str, Any]:
    """Copy of a question whose right answer sits at position `slot % len(options)`.

    The hand-written bank keeps every right answer at "a" or "b": answering "b" to everything scored
    about 55%. Callers pass the question's index, so positions cycle a, b, c, d and a constant answer
    scores about 1/len(options). Distractors are shuffled with an RNG seeded by the question text,
    so reseeding gives the same bank.
    """
    options = list(question["options"])
    correct = next(o for o in options if o["id"] == question["correct_option"])
    distractors = [o for o in options if o is not correct]
    random.Random(question["question_text"]).shuffle(distractors)
    position = slot % len(options)
    ordered = distractors[:position] + [correct] + distractors[position:]
    letters = "abcdefgh"
    relettered = [{"id": letters[i], "text": o["text"]} for i, o in enumerate(ordered)]
    return {**question, "options": relettered, "correct_option": letters[position]}


async def seed_questions() -> None:
    from sqlalchemy import func, select

    from app.core.database import AsyncSessionLocal
    from app.models.assessment import TestQuestion

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(select(func.count()).select_from(TestQuestion))
        existing = count_result.scalar_one()
        if existing > 0:
            print(f"Question bank already has {existing} questions — skipping seed.")
            return

        for slot, raw in enumerate(QUESTIONS):
            q = balanced(raw, slot)
            db.add(TestQuestion(
                id=uuid.uuid4(),
                discipline=q["discipline"],
                target_grade=q["target_grade"],
                question_type="mcq",
                question_text=q["question_text"],
                options=q["options"],
                correct_option=q["correct_option"],
                difficulty=q["difficulty"],
                discrimination=1.0,
                active=True,
            ))

        await db.commit()
        print(f"Seeded {len(QUESTIONS)} test questions.")


if __name__ == "__main__":
    asyncio.run(seed_questions())

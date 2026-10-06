# Сборка, развёртывание и локальный запуск

Инструкция для эксперта, который разворачивает решение на своей машине (ТЗ 3.3, 3.4). Один и тот же путь каждый раз проходит в CI: задание `compose-e2e` выполняет `make demo` и `make check` на чистой машине.

Время первого запуска — 5–10 минут: столько уходит на сборку образов. Повторный запуск занимает меньше минуты.

## 1. Что понадобится

| Что | Версия | Как проверить |
|---|---|---|
| Docker Engine или Docker Desktop | 24 и новее | `docker --version` |
| Docker Compose v2 | 2.17 и новее (нужен флаг `--wait`) | `docker compose version` |
| Git | любая | `git --version` |
| Свободная память | 4 ГБ | всё вместе занимает около 1,5 ГБ |
| Место на диске | 5 ГБ | образы и зависимости |
| Свободные порты | 80 и 8025 | порт 80 можно поменять, см. раздел 9 |

`make` нужен только для коротких команд. В Windows его обычно нет, поэтому для PowerShell рядом даны те же команды без `make`.

Подходит Linux, macOS (Intel и Apple Silicon) и Windows 10/11 с Docker Desktop на WSL 2. Python и Node.js на машине не нужны: всё собирается внутри контейнеров.

## 2. Получить код

```bash
git clone https://github.com/KonkovDV/fsp-talent.git
cd fsp-talent
```

Если код пришёл архивом, распакуйте его и откройте терминал в папке `fsp-talent`.

## 3. Запустить одной командой

**Linux и macOS**

```bash
make demo
```

**Windows (PowerShell)**

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build --wait
docker compose exec -T -u appuser backend python -m seed.generate_seed
```

`make demo` выполняет те же три шага:

1. Создаёт `.env` из `.env.example`, если файла ещё нет. Править его не нужно. Ключ подписи токенов контейнер сам создаст при первом старте и сохранит в томе `vc_keys`.
2. Собирает образы, поднимает контейнеры и ждёт, пока контейнеры с проверкой здоровья (база, backend, worker, beat, frontend, Mailpit) станут `healthy`. Миграции базы применяются при старте backend.
3. Загружает демо-данные. Повторный запуск безопасен: уже загруженное не дублируется.

В конце команда печатает адреса и демо-входы.

## 4. Проверить, что всё работает

| Адрес | Что там |
|---|---|
| http://localhost | Сайт: кабинеты кандидата и работодателя |
| http://localhost/docs | Swagger UI: все методы API с запросами, ответами и кодами ошибок |
| http://localhost/openapi.json | Спецификация OpenAPI 3.1 |
| http://localhost/health | `{"status":"ok",...}` |
| http://localhost:8025 | Mailpit: письма с кодами подтверждения и уведомлениями |

Команда `docker compose ps` должна показать восемь контейнеров в состоянии `running`. У всех, кроме `redis` и `nginx`, дополнительно стоит `healthy`.

Сквозная проверка API на запущенном стенде:

```bash
make check
```

Команда регистрирует нового кандидата (код подтверждения она берёт из Mailpit), привязывает ФСП ID через демо-провайдера, проходит адаптивный тест, ищет кандидата, отправляет приглашение и проверяет раскрытие контактов. Успешный прогон заканчивается строкой `SMOKE OK`.

> `make check` меняет демо-данные: например, повышает грейд кандидата `fsp001@demo.talent`. Чтобы вернуть стенд к исходному виду, выполните `make reset` и снова `make demo`.

## 5. Демо-входы

Пароль у всех демо-аккаунтов: `demo12345`. Компании и люди вымышленные.

| Роль | Email | Что показывает |
|---|---|---|
| Кандидат | `fsp001@demo.talent` | Привязан ФСП ID, результаты из протоколов, ожидающие приглашения с зарплатой, задача недели |
| Кандидат | `fsp002@demo.talent` | Специализация «информационная безопасность», командные результаты ФСП |
| Кандидат | `nofsp@demo.talent` | Без истории ФСП: категория строится только по опросу и тесту |
| Работодатель | `hr@sibcode.demo` | Три потребности с подборками, приглашения во всех статусах, вакансии и отклики |

Чтобы показать регистрацию с нуля, заведите новый аккаунт на http://localhost/register. Код подтверждения придёт в Mailpit. Для привязки ФСП ID в демо-реестре свободны номера FSP2000–FSP2099, пароль `test`.

Пошаговый сценарий показа — в [README](../README.md#сквозной-сценарий-из-тз-33).

## 6. Тесты и проверки

Все команды запускаются на поднятом стенде, внутри контейнера backend.

| Что | Linux, macOS | Windows (PowerShell) |
|---|---|---|
| Юнит-тесты | `make test` | `docker compose exec -T backend python -m pytest tests/unit -q` |
| Стиль кода | `make lint` | `docker compose exec -T backend sh -c "pip install -q ruff==0.16.10 && ruff check app seed tests"` |
| Проверка теста и подбора на синтетике | `make validate` | `docker compose exec -T backend python -m app.validation.assessment --n 300 --seed 7 --check` |
| Сквозная проверка API | `make check` | `docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/smoke_api.py` |
| Нагрузка: 40 пользователей в течение минуты | `make load` | `docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/load_api.py` |

Внутри контейнера нет Node.js, Go, Java, Kotlin и .NET, поэтому тесты, которые перезапускают задания на этих языках, пропускаются с пометкой `skipped`. В CI все языки установлены и эти тесты выполняются.

Полные цифры из документации воспроизводятся так:

```bash
docker compose exec -T backend python -m app.validation.assessment --n 2000 --seed 7
docker compose exec -T backend python -m app.validation.matching
docker compose exec -T backend python -m app.validation.matching --seed 7
```

## 7. Остановить, сбросить, обновить

| Действие | Команда |
|---|---|
| Остановить, данные сохраняются | `make down` или `docker compose down` |
| Запустить снова | `make up` или `docker compose up -d --wait` |
| Удалить все данные (база, ключи) | `make reset` или `docker compose down -v` |
| Обновить код и пересобрать | `git pull`, затем `make demo` |
| Журнал API | `make logs` или `docker compose logs -f backend` |
| Консоль базы | `docker compose exec postgres psql -U fsp fsp_talent` |

## 8. Что входит в стенд

| Контейнер | Образ | Назначение |
|---|---|---|
| `nginx` | nginx:alpine | Единая точка входа: сайт, `/api`, `/docs`, заголовки безопасности (CSP) |
| `frontend` | собирается из `frontend/` (node:20 → nginx) | React-приложение для обеих ролей |
| `backend` | собирается из `backend/` (python:3.12-slim) | FastAPI, миграции Alembic при старте, 2 процесса uvicorn |
| `worker` | тот же образ | Celery: пересчёт профилей, истечение приглашений, задача недели, удаление данных по 152-ФЗ |
| `beat` | тот же образ | Расписание задач Celery |
| `postgres` | pgvector/pgvector:pg16 | PostgreSQL 16 с pgvector и pg_trgm |
| `redis` | redis:7.2-alpine | Лимиты запросов, состояние входа через ФСП ID, брокер Celery |
| `mailpit` | axllent/mailpit | Почтовый ящик для писем на локальном стенде |

Наружу открыт только порт nginx. API (8010), отдельный frontend (3010) и Mailpit (8025) слушают только 127.0.0.1. У базы и Redis портов на хосте нет.

## 9. Настройки `.env`

Для демо `.env` можно не трогать. Основные параметры:

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `SECRET_KEY` | заглушка | Ключ подписи токенов. Заглушку контейнер заменит случайным ключом. На публичном стенде задайте свой: `openssl rand -hex 32` |
| `HTTP_PORT` | 80 | Порт сайта на хосте. Если 80 занят: `HTTP_PORT=8080` и `PUBLIC_BASE_URL=http://localhost:8080` |
| `PUBLIC_BASE_URL` | http://localhost | Адрес, из которого строятся ссылки в письмах |
| `FSP_MODE` | mock | `mock` — тестовый реестр ФСП, `real` — HTTP-клиент по контракту из [FSP_INTEGRATION.md](FSP_INTEGRATION.md) |
| `FSP_ID_MODE` | mock | `mock` — демо-страница провайдера, `oidc` — Keycloak Федерации (`FSP_ID_ISSUER`, `FSP_ID_CLIENT_ID`, `FSP_ID_CLIENT_SECRET`) |
| `AI_ENABLED`, `GIGACHAT_CREDENTIALS` | true, пусто | Без ключа GigaChat резюме разбирается правилами. С ключом модель только добавляет навыки с дословной цитатой |
| `EMBEDDINGS_MODE` | off | `model` включает смысловой поиск по эмбеддингам. Нужны зависимости `.[ai]` (sentence-transformers и torch), в демо-образ они не входят |
| `MAIL_MODE`, `SMTP_*` | smtp → Mailpit | Настоящий SMTP на стенде |

## 10. Запуск без Docker (для разработки)

Нужны Python 3.12, Node.js 20+, PostgreSQL 16 с расширением pgvector и Redis 7.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -c requirements.lock -e ".[test]"
export DATABASE_URL=postgresql+asyncpg://fsp:fsp@localhost:5432/fsp_talent
export REDIS_URL=redis://localhost:6379/0
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export MAIL_MODE=console VC_PRIVATE_KEY_PATH=./vc_ed25519.pem
alembic upgrade head
python -m seed.generate_seed
uvicorn app.main:app --reload --port 8000

# frontend, в другом терминале
cd frontend
npm ci
npm run dev        # http://localhost:5173, запросы /api уходят на :8000
```

Коды подтверждения при `MAIL_MODE=console` печатаются в журнал uvicorn.

## 11. Публичный стенд с HTTPS

Продовая сборка (`deploy/docker-compose.prod.yml`) использует Caddy с автоматическим сертификатом Let's Encrypt и ночные резервные копии базы. Домен покупать не нужно: подходит адрес вида `203-0-113-10.sslip.io`. Шаги описаны в [deploy/README.md](../deploy/README.md).

## 12. Если что-то пошло не так

| Симптом | Причина и решение |
|---|---|
| `port is already allocated` для 80 | Порт занят другим сервером. Задайте в `.env` `HTTP_PORT=8080` и `PUBLIC_BASE_URL=http://localhost:8080`, затем `make demo` |
| `unknown flag: --wait` | Compose старше 2.17. Обновите Docker Desktop или запустите без флага и подождите минуту: `docker compose up -d --build` |
| `env file .env not found` | Не создан `.env`. Выполните `cp .env.example .env` (Windows: `Copy-Item .env.example .env`) |
| `backend` не становится `healthy` | Посмотрите `docker compose logs backend`. Если там `SECRET_KEY is a published placeholder`, том `vc_keys` недоступен на запись: задайте `SECRET_KEY` в `.env` |
| Вход не работает, `503` | Redis не запущен: `docker compose ps redis`, затем `docker compose up -d redis` |
| Письмо с кодом не пришло | Откройте Mailpit http://localhost:8025. Код можно запросить повторно через минуту |
| После `git pull` сайт показывает старую версию | Пересоберите образы: `make demo` (или `docker compose up -d --build --wait`) |
| Нужен чистый стенд | `make reset`, затем `make demo` |
| Сборка падает на `npm ci` или `pip install` | Нет доступа к npm или PyPI. Проверьте прокси Docker Desktop (Settings → Resources → Proxies) |

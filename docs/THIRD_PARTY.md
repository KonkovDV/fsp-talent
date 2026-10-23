# Сторонние компоненты и лицензии

Здесь перечислено всё стороннее, что входит в решение или используется при сборке. Собственный код решения открыт под лицензией [MIT](../LICENSE). Все компоненты ниже — открытое ПО или открытые материалы; закрытых библиотек и обфусцированного кода в решении нет.

Версии — те, на которых проходят тесты: backend ставит пакеты из `backend/requirements.lock`, frontend — из `frontend/package-lock.json`, инструменты документации — из `docs/tools/package-lock.json`. Лицензии взяты из метаданных пакетов (PyPI, поле `license` в `package-lock.json`).

## Backend (Python 3.12)

| Пакет | Версия | Лицензия | Зачем |
|---|---|---|---|
| FastAPI | 0.142.2 | MIT | HTTP API, OpenAPI |
| Starlette | 1.7.0 | BSD-3-Clause | ASGI-основа FastAPI |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI-сервер |
| Pydantic | 2.13.5 | MIT | Схемы и валидация |
| pydantic-settings | 2.15.0 | MIT | Настройки из окружения |
| SQLAlchemy | 2.1.3 | MIT | ORM, асинхронный доступ |
| asyncpg | 0.31.0 | Apache-2.0 | Драйвер PostgreSQL |
| Alembic | 1.20.0 | MIT | Миграции |
| pgvector (Python) | 0.5.0 | MIT | Тип vector |
| redis-py | 6.4.0 | MIT | Лимиты, состояние входа ФСП ID |
| Celery | 5.6.3 | BSD-3-Clause | Фоновые задачи и расписание |
| PyJWT | 2.15.1 | MIT | JWT, проверка ID-токена ФСП ID |
| argon2-cffi | 25.1.0 | MIT | Хеши паролей Argon2id |
| bcrypt | 5.0.0 | Apache-2.0 | Проверка старых хешей при входе |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Ed25519, AES-256-GCM |
| httpx | 0.28.1 | BSD-3-Clause | Клиент реестра ФСП и Keycloak |
| pypdf | 6.21.1 | BSD-3-Clause | Текст из PDF-резюме |
| fpdf2 | 2.8.9 | LGPL-3.0-only | PDF-профиль кандидата; используется как библиотека без изменений |

fpdf2 распространяется по LGPL-3.0. Решение не меняет его исходный код и не встраивает его в свой: пакет ставится из PyPI отдельной зависимостью (`fpdf2==2.8.9` в `backend/requirements.lock`) и подключается обычным импортом Python во время работы (`from fpdf import FPDF` в `app/services/pdf_profile.py`). Это динамическое связывание в смысле LGPL: любой получатель может заменить библиотеку своей сборкой той же или совместимой версии, поменяв строку в lock-файле и пересобрав образ backend, а лицензия на собственный код решения от этого не зависит.

Только для тестов и проверки кода:

| Пакет | Версия | Лицензия |
|---|---|---|
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| pytest-cov | 7.1.0 | MIT |
| Hypothesis | 6.140.4 | MPL-2.0 |

Версии выше — из `backend/requirements.lock`. Линтер Ruff (MIT) в lock-файл не входит: версия 0.16.10 закреплена в `.github/workflows/ci.yml` и `Makefile` (`pip install ruff==0.16.10`), в `pyproject.toml` указан нижний предел `ruff>=0.4`.

Необязательные, в образ стенда не входят: `gigachat` ≥ 0.1.39 (MIT, клиент GigaChat), `sentence-transformers` ≥ 3.0 (Apache-2.0) и `torch` ≥ 2.3 (BSD-3-Clause) для смыслового поиска — ставятся аргументом сборки `INSTALL_RERANKER=1`.

## Frontend (Node.js 20)

| Пакет | Версия | Лицензия | Зачем |
|---|---|---|---|
| React, React DOM | 18.3.1 | MIT | Интерфейс |
| React Router DOM | 6.30.6 | MIT | Маршруты |
| TanStack Query | 5.104.1 | MIT | Запросы и кеш |
| Zustand | 4.5.7 | MIT | Состояние входа |
| React Hook Form | 7.89.0 | MIT | Формы |
| Zod | 3.25.76 | MIT | Проверка данных форм |
| @hookform/resolvers | 3.10.0 | MIT | Связка форм и Zod |
| Axios | 1.20.0 | MIT | HTTP-клиент |
| lucide-react | 0.447.0 | ISC | Иконки |
| qrcode-generator | 2.0.4 | MIT | QR-код паспорта навыков |
| date-fns | 3.6.0 | MIT | Даты |
| clsx, tailwind-merge | 2.1.1, 2.6.1 | MIT | Классы CSS |
| @fontsource-variable/golos-text, jetbrains-mono | 5.3.0 | OFL-1.1 | Шрифты, раздаются с того же адреса, без внешних запросов |

Сборка и тесты интерфейса:

| Пакет | Версия | Лицензия |
|---|---|---|
| Vite | 6.4.3 | MIT |
| @vitejs/plugin-react | 4.7.0 | MIT |
| TypeScript | 5.9.3 | Apache-2.0 |
| Tailwind CSS | 3.4.19 | MIT |
| PostCSS, Autoprefixer | 8.5.28, 10.6.1 | MIT |
| Vitest | 5.0.3 | MIT |
| Testing Library (react, jest-dom, user-event) | 16.3.3, 7.0.1, 14.6.7 | MIT |
| jsdom | 29.1.1 | MIT |
| Playwright Test | 1.63.0 | Apache-2.0 |
| @axe-core/playwright | 4.13.0 | MPL-2.0 |

## Образы контейнеров и инфраструктура

| Компонент | Образ или версия | Лицензия | Где |
|---|---|---|---|
| PostgreSQL с pgvector и pg_trgm | `pgvector/pgvector:pg16` | PostgreSQL License | База, контейнер резервных копий |
| Redis | `redis:7.2-alpine` | BSD-3-Clause | Лимиты, брокер Celery |
| nginx | `nginx:1.28-alpine` | BSD-2-Clause | Вход локального стенда, раздача frontend |
| Caddy | `caddy:2.10-alpine` | Apache-2.0 | HTTPS на сервере |
| Mailpit | `axllent/mailpit:v1.31.4` | MIT | Почтовый ящик локального стенда |
| Keycloak | `quay.io/keycloak/keycloak:26.0.7` | Apache-2.0 | Проверка настоящего OIDC, профиль `fsp-id` |
| Python | `python:3.12-slim`, `python:3.12-slim-bookworm` | PSF-2.0 | Образы backend и sandbox |
| Node.js | `node:20-alpine`, `node:20-bookworm-slim` | MIT | Сборка frontend; бинарник node в sandbox |
| Swagger UI | `swagger-ui-dist` 5.33.1, лежит в `backend/app/static/swagger-ui/` вместе с LICENSE и NOTICE | Apache-2.0 | Страница `/docs` |

## Инструменты документации

| Компонент | Версия | Лицензия | Зачем |
|---|---|---|---|
| Mermaid | 11.17.2 | MIT | Схемы в PDF документации |
| Matplotlib | 3.11.2 | Matplotlib License (на основе PSF) | Рисунки проверки (`docs/tools/make_figures.py`) |
| PptxGenJS | 4.0.1 | MIT | Слайды презентации |
| python-pptx | 1.0.2 | MIT | Сборка презентации |

## Модели и внешние сервисы

| Что | Лицензия или условия | Как используется |
|---|---|---|
| GigaChat (Сбер), YandexGPT (Яндекс) | Условия облачных провайдеров | Необязательно, по умолчанию выключено (`AI_ENABLED`). Получает обезличенный текст; балл, порядок выдачи и грейд не меняет |
| `BAAI/bge-reranker-v2-m3` | Apache-2.0 | Необязательная локальная модель пары; веса в репозиторий не входят и на стенде не используются |
| sslip.io | Публичный DNS-сервис | Имя сервера вида `203-0-113-10.sslip.io` без покупки домена |
| Let's Encrypt | Условия ISRG | Сертификат TLS, его получает Caddy |

## Материалы

- Фирменная палитра и стиль интерфейса — по брендбуку Федерации спортивного программирования; использование брендбука разрешено организаторами спецтрека.
- Демо-компании, кандидаты, вакансии и протоколы соревнований вымышлены и сгенерированы `backend/seed/`.
- Задания теста — собственные параметрические семейства решения (`backend/app/items/`).

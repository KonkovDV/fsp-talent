# Лицензии сторонних компонентов (THIRD_PARTY_NOTICES)

Проект «ФСП Талант» распространяется по лицензии MIT (`LICENSE`). Ниже перечислены сторонние компоненты и их лицензии. Права на компоненты принадлежат их авторам; тексты лицензий входят в пакеты. Краткий перечень с назначением пакетов — [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

Как получен список:
- backend: версии — из `backend/requirements.lock` (все 97 строк). Рабочая сборка — 88 пакетов: зависимости `[project].dependencies` из `backend/pyproject.toml` с extras и транзитивными. Остальные 9 нужны только тестам (`.[test]`) и вынесены в отдельную таблицу. Лицензия — из метаданных пакета (`License-Expression`, классификатор `License ::` или поле `License`);
- frontend: `frontend/package-lock.json`, пакеты без флага `dev` — 52; лицензия — поле `license` в lock-файле. Пакеты сборки и тестов (254, флаг `dev`) в браузер не попадают и в таблицу не входят.

## Итог проверки на copyleft

- **GPL/AGPL: нет** ни в backend, ни во frontend.
- **LGPL-3.0-only: `fpdf2`** (генерация PDF). Библиотека используется без изменений, как отдельный пакет Python, поэтому условия LGPL выполняются: пользователь может заменить её своей версией. Исходный код проекта открыт по MIT.
- **MPL-2.0**: `certifi` в рабочей сборке backend и `hypothesis` только в тестах; слабый copyleft на уровне файла, файлы пакетов не изменялись.
- **OFL-1.1** (шрифты во frontend): атрибуция сохраняется в пакетах.

Сводка frontend по лицензиям: MIT — 49, OFL-1.1 — 2, ISC — 1.

## Backend (Python): рабочая сборка

| Пакет | Версия | Лицензия |
|---|---|---|
| agent-detector | 2.0.0 | MIT |
| alembic | 1.20.0 | MIT |
| amqp | 5.4.1 | BSD License |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| asyncpg | 0.31.0 | Apache-2.0 |
| bcrypt | 5.0.0 | Apache Software License |
| billiard | 4.3.1 | BSD License |
| celery | 5.6.3 | BSD-3-Clause |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| click-didyoumean | 0.3.1 | MIT License |
| click-plugins | 1.1.1.2 | BSD License |
| click-repl | 0.4.1 | MIT |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| defusedxml | 0.7.1 | Python Software Foundation License |
| detect-installer | 0.2.1 | 0BSD |
| dnspython | 2.8.0 | ISC License (ISCL) |
| email-validator | 2.3.0 | The Unlicense (Unlicense) |
| fastapi | 0.142.2 | MIT |
| fastapi-cli | 0.0.32 | MIT |
| fastapi-cloud-cli | 0.26.0 | MIT License |
| fastar | 0.12.0 | MIT |
| fonttools | 4.66.1 | MIT |
| fpdf2 | 2.8.9 | LGPL-3.0-only |
| googleapis-common-protos | 1.75.5 | Apache-2.0 |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httptools | 0.8.0 | MIT |
| httpx | 0.28.1 | BSD License |
| idna | 3.20 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD License |
| kombu | 5.6.2 | BSD-3-Clause |
| mako | 1.4.3 | MIT |
| markdown-it-py | 4.2.0 | MIT License |
| markupsafe | 3.0.4 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT License |
| opentelemetry-api | 1.45.0 | Apache-2.0 |
| opentelemetry-exporter-http-transport | 0.66b0 | Apache-2.0 |
| opentelemetry-exporter-otlp-common | 0.66b0 | Apache-2.0 |
| opentelemetry-exporter-otlp-proto-common | 1.45.0 | Apache-2.0 |
| opentelemetry-exporter-otlp-proto-http | 1.45.0 | Apache-2.0 |
| opentelemetry-proto | 1.45.0 | Apache-2.0 |
| opentelemetry-sdk | 1.45.0 | Apache-2.0 |
| opentelemetry-semantic-conventions | 0.66b0 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pgvector | 0.5.0 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| prompt-toolkit | 3.0.53 | BSD License |
| protobuf | 7.36.2 | 3-Clause BSD License |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.5 | MIT |
| pydantic-core | 2.46.5 | MIT |
| pydantic-extra-types | 2.11.1 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pypdf | 6.19.0 | BSD-3-Clause |
| python-dateutil | 2.9.0.post0 | BSD License; Apache Software License |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pyyaml | 6.0.3 | MIT License |
| redis | 6.4.0 | MIT |
| rich | 15.0.0 | MIT License |
| rich-toolkit | 0.20.5 | MIT |
| rignore | 0.8.1 | MIT |
| sentry-sdk | 2.71.0 | MIT |
| shellingham | 1.5.4 | ISC License (ISCL) |
| six | 1.17.0 | MIT License |
| sqlalchemy | 2.1.3 | MIT |
| starlette | 1.7.0 | BSD-3-Clause |
| typer | 0.27.2 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| tzdata | 2026.5 | Apache-2.0 |
| tzlocal | 5.4.4 | MIT |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| uvloop | 0.23.0 | Apache Software License; MIT License |
| vine | 5.1.0 | BSD License |
| watchfiles | 1.3.0 | MIT License |
| wcwidth | 0.9.2 | MIT License |
| websockets | 17.2 | BSD-3-Clause |

## Backend (Python): только тесты

| Пакет | Версия | Лицензия |
|---|---|---|
| attrs | 26.1.0 | MIT |
| coverage | 7.16.2 | Apache-2.0 |
| hypothesis | 6.140.4 | MPL-2.0 |
| iniconfig | 2.3.0 | MIT |
| pluggy | 1.6.0 | MIT License |
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| pytest-cov | 7.1.0 | MIT |
| sortedcontainers | 2.4.0 | Apache Software License |

## Frontend (JavaScript): попадает в браузер

| Пакет | Версия | Лицензия |
|---|---|---|
| @fontsource-variable/golos-text | 5.3.0 | OFL-1.1 |
| @fontsource-variable/jetbrains-mono | 5.3.0 | OFL-1.1 |
| @hookform/resolvers | 3.10.0 | MIT |
| @remix-run/router | 1.23.4 | MIT |
| @tanstack/query-core | 5.104.1 | MIT |
| @tanstack/react-query | 5.104.1 | MIT |
| @types/prop-types | 15.7.15 | MIT |
| @types/react | 18.3.31 | MIT |
| agent-base | 6.0.2 | MIT |
| asynckit | 0.4.0 | MIT |
| axios | 1.20.0 | MIT |
| call-bind-apply-helpers | 1.0.2 | MIT |
| clsx | 2.1.1 | MIT |
| combined-stream | 1.0.8 | MIT |
| csstype | 3.2.3 | MIT |
| date-fns | 3.6.0 | MIT |
| debug | 4.4.3 | MIT |
| delayed-stream | 1.0.0 | MIT |
| dunder-proto | 1.0.1 | MIT |
| es-define-property | 1.0.1 | MIT |
| es-errors | 1.3.0 | MIT |
| es-object-atoms | 1.1.2 | MIT |
| es-set-tostringtag | 2.1.0 | MIT |
| follow-redirects | 1.16.1 | MIT |
| form-data | 4.0.6 | MIT |
| function-bind | 1.1.2 | MIT |
| get-intrinsic | 1.3.0 | MIT |
| get-proto | 1.0.1 | MIT |
| gopd | 1.2.0 | MIT |
| has-symbols | 1.1.0 | MIT |
| has-tostringtag | 1.0.2 | MIT |
| hasown | 2.0.4 | MIT |
| https-proxy-agent | 5.0.1 | MIT |
| js-tokens | 4.0.0 | MIT |
| loose-envify | 1.4.0 | MIT |
| lucide-react | 0.447.0 | ISC |
| math-intrinsics | 1.1.0 | MIT |
| mime-db | 1.52.0 | MIT |
| mime-types | 2.1.35 | MIT |
| ms | 2.1.3 | MIT |
| proxy-from-env | 2.1.0 | MIT |
| qrcode-generator | 2.0.4 | MIT |
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-hook-form | 7.89.0 | MIT |
| react-router | 6.30.6 | MIT |
| react-router-dom | 6.30.6 | MIT |
| scheduler | 0.23.2 | MIT |
| tailwind-merge | 2.6.1 | MIT |
| use-sync-external-store | 1.7.0 | MIT |
| zod | 3.25.76 | MIT |
| zustand | 4.5.7 | MIT |

# Репозиторий

https://github.com/KonkovDV/fsp-talent — публичный репозиторий, код открыт под лицензией [MIT](../../LICENSE).

## Стек

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, PostgreSQL 16 с pgvector, Redis 7.2, React 18, Vite 6, TypeScript, Tailwind CSS. Всё поднимается в Docker Compose: девять сервисов и разовый загрузчик демо-данных, видеокарта не нужна. Схема сервисов — в [README](../../README.md#как-устроено), ключевые решения коротко — в [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Запуск одной командой

Нужны Docker 24+ с Compose 2.24+, 4 ГБ свободной памяти и свободные порты 80 и 8025.

```bash
git clone https://github.com/KonkovDV/fsp-talent.git
cd fsp-talent
docker compose up -d --build --wait
```

Команда собирает контейнеры, применяет миграции и загружает демо-данные. Первый запуск занимает 5–10 минут. Потом открываются http://localhost (сайт), http://localhost/docs (Swagger UI) и http://localhost:8025 (Mailpit, письма с кодами). С `make` то же самое: `make demo`.

На Windows без make: `powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1`. Подробности, развёртывание на сервере и частые проблемы — в [docs/INSTALL.md](../../docs/INSTALL.md).

## Где тесты

| Что | Где | Команда |
|---|---|---|
| Юнит-тесты backend | [backend/tests/unit](../../backend/tests/unit) | `make test` |
| Требования без базы | [docs/requirements_trace.md](../../docs/requirements_trace.md) | `make accept` |
| Сквозной сценарий API на запущенном стенде | [backend/tests/smoke_api.py](../../backend/tests/smoke_api.py) | `make check` (печатает `SMOKE OK`) |
| Самопроверка демо-данных | `backend/seed/demo_check.py` | `make demo-check` |
| Тест и подбор на синтетике, с порогами | `backend/app/validation` | `make validate` |
| Нагрузка: 40 пользователей минуту | [backend/tests/load_api.py](../../backend/tests/load_api.py) | `make load` |
| Интерфейс | [frontend](../../frontend) | `npm test` и `npx playwright test` в `frontend/` |
| Числа в документации против свежего прогона | [backend/tests/doc_numbers.py](../../backend/tests/doc_numbers.py) | `python tests/doc_numbers.py` в `backend/` |

Те же проверки идут в CI на каждый пуш в `main`, они записаны в [.github/workflows/ci.yml](../../.github/workflows/ci.yml). Как внести изменение — [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Что мы измерили и где границы

- Юнит-тестов 1805 (`python -m pytest tests/unit --collect-only -q`), тестов интерфейса 221, проверок Playwright 67. Цифры из корневого README, их сверяет `tests/doc_numbers.py`.
- Платформа встаёт одной командой: тест, подбор, удостоверения. Реестр ФСП и ФСП ID говорят на боевом контракте, на демо-стенде они работают через демо-провайдер.

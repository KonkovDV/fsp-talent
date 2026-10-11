# Репозиторий

**Ссылка для формы:** https://github.com/KonkovDV/fsp-talent

Репозиторий публичный, код открыт под лицензией [MIT](../../LICENSE).

## Стек

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, PostgreSQL 16, Redis 7.2, React 18, Vite 6, TypeScript, Tailwind CSS. Всё поднимается в Docker Compose: девять контейнеров, видеокарта не нужна. Схема сервисов — в [README](../../README.md#архитектура), ключевые решения коротко — в [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Запуск одной командой

Нужны Docker 24+ с Compose 2.17+, 4 ГБ свободной памяти и свободные порты 80 и 8025.

```bash
git clone https://github.com/KonkovDV/fsp-talent.git
cd fsp-talent
make demo
```

`make demo` сам создаёт `.env`, собирает контейнеры, применяет миграции и загружает демо-данные. Первый запуск занимает 5–10 минут. Потом открываются http://localhost (сайт), http://localhost/docs (Swagger UI) и http://localhost:8025 (Mailpit, письма с кодами).

На Windows без make: `powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1`. Подробности, развёртывание на сервере и частые проблемы — в [docs/INSTALL.md](../../docs/INSTALL.md).

## Где тесты

| Что | Где | Команда |
|---|---|---|
| Юнит-тесты backend | [backend/tests/unit](../../backend/tests/unit) | `make test` |
| Требования ТЗ без базы | [docs/requirements_trace.md](../../docs/requirements_trace.md) | `make accept` |
| Сквозной сценарий API на запущенном стенде | [backend/tests/smoke_api.py](../../backend/tests/smoke_api.py) | `make check` (печатает `SMOKE OK`) |
| Самопроверка демо-данных | `backend/seed/demo_check.py` | `make demo-check` |
| Тест и подбор на синтетике, с порогами | `backend/app/validation` | `make validate` |
| Нагрузка: 40 пользователей минуту | [backend/tests/load_api.py](../../backend/tests/load_api.py) | `make load` |
| Интерфейс | [frontend](../../frontend) | `npm test` и `npx playwright test` в `frontend/` |
| Числа в документации против свежего прогона | [backend/tests/doc_numbers.py](../../backend/tests/doc_numbers.py) | `python tests/doc_numbers.py` в `backend/` |

Тот же набор проверок идёт перед каждым слиянием в `main`, он записан в [.github/workflows/ci.yml](../../.github/workflows/ci.yml).

## Что мы измерили и где границы

- Юнит-тестов 1117 (`python -m pytest tests/unit --collect-only -q`), тестов интерфейса 110, проверок Playwright 67. Цифры из корневого README, их сверяет `tests/doc_numbers.py`.
- Мы сделали MVP под ТЗ хакатона, промышленная установка будет у Федерации. Реестр ФСП и ФСП ID подключены через адаптеры с флагом режима, на стенде работают их демо-версии.

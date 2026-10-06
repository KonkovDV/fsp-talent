# Короткие команды для локального запуска. Без make те же шаги описаны в docs/INSTALL.md.
.PHONY: help demo up down reset seed logs test lint check validate load

help:
	@echo "make demo      — собрать, запустить и загрузить демо-данные (первый запуск)"
	@echo "make up        — запустить уже собранные контейнеры"
	@echo "make down      — остановить, данные сохраняются"
	@echo "make reset     — остановить и удалить данные (база, ключи)"
	@echo "make seed      — загрузить демо-данные ещё раз (повтор безопасен)"
	@echo "make logs      — журнал API"
	@echo "make test      — юнит-тесты внутри контейнера"
	@echo "make lint      — проверка стиля Python"
	@echo "make validate  — проверка адаптивного теста и подбора на синтетике"
	@echo "make check     — сквозная проверка API на запущенном стенде"
	@echo "make load      — 40 пользователей одновременно в течение минуты"

demo:
	@test -f .env || cp .env.example .env
	docker compose up -d --build --wait
	docker compose exec -T -u appuser backend python -m seed.generate_seed
	@echo ""
	@echo "Готово. Сайт: http://localhost  API: http://localhost/docs  Почта: http://localhost:8025"
	@echo "Демо-входы, пароль demo12345: fsp001@demo.talent (кандидат), hr@sibcode.demo (работодатель)"

up:
	@test -f .env || cp .env.example .env
	docker compose up -d --wait

down:
	docker compose down

reset:
	docker compose down -v

seed:
	docker compose exec -T -u appuser backend python -m seed.generate_seed

logs:
	docker compose logs -f backend

test:
	docker compose exec -T backend python -m pytest tests/unit -q

lint:
	docker compose exec -T backend sh -c "pip install -q ruff==0.16.10 && ruff check app seed tests"

validate:
	docker compose exec -T backend python -m app.validation.assessment --n 300 --seed 7 --check
	docker compose exec -T backend python -m app.validation.matching

check:
	docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/smoke_api.py

load:
	docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/load_api.py --users 40 --seconds 60

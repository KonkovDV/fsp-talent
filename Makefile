.PHONY: up down build migrate seed test lint shell logs

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec -u appuser backend python -m seed.generate_seed

test:
	docker compose exec backend pytest tests/unit/ -v --cov=app/services --cov-report=term-missing

test-all:
	docker compose exec backend pytest tests/ -v --cov=app

lint:
	docker compose exec backend ruff check app/

typecheck:
	docker compose exec backend mypy app/ --ignore-missing-imports

shell:
	docker compose exec backend bash

logs:
	docker compose logs -f backend

worker-logs:
	docker compose logs -f worker

dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

# Короткие команды для локального запуска. Без make те же шаги описаны в docs/INSTALL.md.
# GPU=1 adds docker-compose.gpu.yml (NVIDIA Container Toolkit required). The default runs on any Docker host.
export GIT_SHA ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
COMPOSE := docker compose$(if $(GPU), -f docker-compose.yml -f docker-compose.gpu.yml,)

.PHONY: help doctor demo up down reset seed seed-topup demo-check demo-reset logs test lint check validate evaluate load docs-pdf docs-pitch

help:
	@echo "make doctor    — проверить Docker, память, диск, порты, .env и образы до первого запуска; без Docker: make doctor LOCAL=1"
	@echo "make demo      — собрать, запустить и загрузить демо-данные (первый запуск); с видеокартой: make demo GPU=1"
	@echo "make up        — запустить уже собранные контейнеры"
	@echo "make down      — остановить, данные сохраняются"
	@echo "make reset     — остановить и удалить данные (база, ключи)"
	@echo "make seed      — загрузить демо-данные ещё раз (повтор безопасен)"
	@echo "make seed-topup — только добавить публичные профили в пустые категории (без удаления)"
	@echo "make demo-reset — вернуть пароли и показ жюри (только при DEMO_MODE)"
	@echo "make logs      — журнал API"
	@echo "make test      — юнит-тесты внутри контейнера"
	@echo "make lint      — проверка стиля Python"
	@echo "make validate  — проверка адаптивного теста и подбора на синтетике"
	@echo "make evaluate — проверка стенда, набор жюри и полные прогоны теста на 2000 и 5000"
	@echo "make check     — сквозная проверка API на запущенном стенде"
	@echo "make load      — 40 пользователей одновременно в течение минуты"
	@echo "make docs-pdf  — собрать docs/FSP_Talent_documentation.pdf (нужны Python, Node.js и Chromium)"
	@echo "make docs-pitch — собрать старый черновик docs/pitch.html и docs/pitch.pptx (сданная презентация — submission/03-presentation)"

doctor:
	@LOCAL=$(LOCAL) bash scripts/doctor.sh

demo:
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --wait
	@echo ""
	@echo "Готово. Сайт: http://localhost  API: http://localhost/docs  Почта: http://localhost:8025"
	@echo "Демо-входы, пароль demo12345: fsp001@demo.talent (кандидат), hr@sibcode.demo (работодатель)"

up:
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --wait

down:
	docker compose down

reset:
	docker compose down -v

seed-topup:
	docker compose exec -T -u appuser backend python -m seed.topup_public

seed:
	docker compose exec -T -u appuser backend python -m seed.generate_seed

demo-check:
	docker compose run --rm --no-deps demo-seed python -m seed.demo_check

demo-reset:
	docker compose exec -T -u appuser backend python -m seed.reset_demo

logs:
	docker compose logs -f backend

test:
	docker compose exec -T backend python -m pytest tests/unit -q

lint:
	docker compose exec -T backend sh -c "pip install -q ruff==0.16.10 && ruff check app seed tests"

validate:
	docker compose exec -T backend python -m app.validation.assessment --n 300 --seed 7 --check
	docker compose exec -T backend python -m app.validation.matching --check
	docker compose exec -T backend python -m app.validation.fsp_axis --seeds 3 --check

evaluate: validate
	docker compose exec -T backend python -m app.validation.jury_pack app/validation/resources/jury_profiles.json
	docker compose exec -T backend python -m app.validation.jury_pack app/validation/resources/jury_profiles.csv
	docker compose exec -T backend python -m app.validation.assessment --n 2000 --seed 7
	docker compose exec -T backend python -m app.validation.assessment --n 5000 --seed 7

check:
	docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/smoke_api.py

accept:
	cd backend && python -m app.validation.accept

load:
	docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 backend python tests/load_api.py --users 40 --seconds 60

load-big:
	sh backend/tests/load_big.sh

docs-pdf:
	test -d docs/tools/node_modules/mermaid || npm install --prefix docs/tools --no-save mermaid@11
	python3 docs/tools/build_pdf.py

docs-pitch:
	node docs/tools/build_pitch.mjs
	python3 docs/tools/build_pitch_template.py

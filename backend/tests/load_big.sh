#!/bin/sh
# Bank of 2000 and 10 000 synthetic profiles, 40 and 100 users, two and four API processes.
# Synthetic profiles are hidden again when the script ends, including after a failed run.
set -e
cd "$(dirname "$0")/../.."
seed() {
  docker compose exec -T -u appuser backend python -m seed.generate_seed --extra-candidates "$1"
}
workers2() {
  docker compose up -d --no-deps --force-recreate --wait backend
}
workers4() {
  docker compose -f docker-compose.yml -f docker-compose.load.yml up -d --no-deps --force-recreate --wait backend
}
run() {
  docker compose exec -T -e SMOKE_BASE=http://localhost:8000/api/v1 -e MAILPIT_URL=http://mailpit:8025 \
    backend python tests/load_api.py "$@"
}
restore() {
  workers2
  seed 0
}
trap restore EXIT
block() {
  bank="$1"
  procs="$2"
  run --users 40 --seconds 60 --reuse --note "банк ${bank}, процессы ${procs}, смешанный, 40 пользователей"
  run --users 100 --seconds 60 --reuse --note "банк ${bank}, процессы ${procs}, смешанный, 100 пользователей"
  run --scenario shortlist --seconds 60 --reuse --note "банк ${bank}, процессы ${procs}, подборка"
}
seed 2000
block 2000 2
workers4
block 2000 4
seed 10000
block 10000 4
workers2
block 10000 2

#!/bin/sh
# Replace the current database with one verified dump.
# Refuses to run until CONFIRM=restore is set. Does not delete Docker volumes.
#
#   CONFIRM=restore sh deploy/restore_db.sh deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump
set -eu

if [ "${CONFIRM:-}" != "restore" ]; then
  echo "Восстановление заменит данные в базе. Повторите так: CONFIRM=restore sh deploy/restore_db.sh путь/к/файлу.dump" >&2
  exit 2
fi

dump=${1:-}
if [ -z "$dump" ] || [ ! -f "$dump" ]; then
  echo "Нужен существующий файл .dump" >&2
  exit 2
fi

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
python "$root/deploy/verify_backup.py" "$dump"

compose=${COMPOSE_FILE:-$root/docker-compose.yml}
envfile=${ENV_FILE:-}
if [ -n "$envfile" ]; then
  docker compose -f "$compose" --env-file "$envfile" exec -T postgres \
    pg_restore -U "${POSTGRES_USER:-fsp}" -d "${POSTGRES_DB:-fsp_talent}" --clean --if-exists --no-owner < "$dump"
else
  docker compose -f "$compose" exec -T postgres \
    pg_restore -U "${POSTGRES_USER:-fsp}" -d "${POSTGRES_DB:-fsp_talent}" --clean --if-exists --no-owner < "$dump"
fi
echo "Восстановление завершено: $dump"

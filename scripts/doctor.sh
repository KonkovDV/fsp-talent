#!/usr/bin/env bash
# Проверка машины перед `make demo` (или перед запуском без Docker с LOCAL=1).
# Печатает ✓ / ✗ / ! и что исправить. Любой ✗ — код выхода 1, «!» только предупреждает.
# Ничего не меняет: не запускает контейнеры, не пишет .env, не скачивает образы.
set -u

cd "$(dirname "$0")/.." || exit 1

FAILS=0
WARNS=0
ok()   { printf '✓ %s\n' "$1"; }
bad()  { printf '✗ %s\n    → %s\n' "$1" "$2"; FAILS=$((FAILS + 1)); }
warn() { printf '! %s\n    → %s\n' "$1" "$2"; WARNS=$((WARNS + 1)); }
have() { command -v "$1" >/dev/null 2>&1; }

# ver_ge 2.17.1 2.17 → 0 (true). Numeric, field by field; non-numeric tails are ignored.
ver_ge() {
  awk -v a="$1" -v b="$2" 'BEGIN {
    na = split(a, x, "."); nb = split(b, y, ".")
    n = (na > nb) ? na : nb
    for (i = 1; i <= n; i++) { xi = x[i] + 0; yi = y[i] + 0
      if (xi > yi) exit 0; if (xi < yi) exit 1 }
    exit 0 }'
}

# First dotted version number in a string: "Docker version 27.3.1, build ce12230" → 27.3.1.
first_version() { grep -oE '[0-9]+(\.[0-9]+)+' <<<"$1" | head -n 1; }

# Value of KEY in .env, without quotes. Empty when the file or the key is missing.
env_value() {
  [ -f .env ] || return 0
  sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" .env | tail -n 1 | sed -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']$//"
}

# 0 when something on this machine already accepts connections on 127.0.0.1:PORT.
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }

with_timeout() {
  if have timeout; then timeout "$@"; else shift; "$@"; fi
}

check_secrets() {
  local key
  key="$(env_value SECRET_KEY)"
  case "$key" in
    ""|change-me-32-chars-minimum-secret|change-me-use-openssl-rand-hex-32)
      if [ "${LOCAL:-}" = 1 ]; then
        if [ -n "${SECRET_KEY:-}" ] && [ ${#SECRET_KEY} -ge 32 ]; then
          ok "SECRET_KEY задан в окружении"
        else
          bad "SECRET_KEY не задан: без Docker ключ из .env.example не заменяется, API не запустится" \
              "export SECRET_KEY=\$(python -c \"import secrets; print(secrets.token_hex(32))\")"
        fi
      else
        ok "SECRET_KEY из .env.example: при первом запуске стенд создаст свой ключ в томе vc_keys"
      fi ;;
    *)
      if [ ${#key} -lt 32 ]; then
        bad "SECRET_KEY в .env короче 32 символов" "openssl rand -hex 32 и вставьте результат в .env"
      else
        ok "SECRET_KEY в .env свой, не из репозитория"
      fi ;;
  esac
  if [ "$(env_value FSP_ID_MODE)" = "oidc" ] && [ "$(env_value FSP_ID_CLIENT_SECRET)" = "fsp-talent-demo" ]; then
    warn "FSP_ID_CLIENT_SECRET — демо-значение из .env.example при FSP_ID_MODE=oidc" \
         "задайте секрет клиента из своего Keycloak"
  fi
}

check_docker() {
  local v mem free_kb running port http_port image
  if ! have docker; then
    bad "docker не найден" "установите Docker Engine 24+ или Docker Desktop: https://docs.docker.com/get-docker/"
    return
  fi
  v="$(first_version "$(docker --version 2>/dev/null)")"
  if [ -n "$v" ] && ver_ge "$v" 24; then ok "docker $v"; else bad "docker ${v:-?}: нужна версия 24 и новее" "обновите Docker"; fi

  if ! docker info >/dev/null 2>&1; then
    bad "демон Docker не отвечает" "запустите Docker Desktop или: sudo systemctl start docker; без sudo — добавьте себя в группу docker"
    return
  fi
  ok "демон Docker отвечает"

  v="$(first_version "$(docker compose version 2>/dev/null)")"
  if [ -z "$v" ]; then
    bad "docker compose v2 не найден (нужна команда «docker compose», не «docker-compose»)" "установите плагин docker-compose-plugin или обновите Docker Desktop"
  elif ver_ge "$v" 2.17; then
    ok "docker compose $v"
  else
    bad "docker compose $v: нужна 2.17 и новее (флаг --wait)" "обновите Docker Desktop или плагин compose"
  fi

  mem="$(docker info --format '{{.MemTotal}}' 2>/dev/null)"
  if [ -n "$mem" ] && [ "$mem" -ge 4000000000 ] 2>/dev/null; then
    ok "память для Docker: $((mem / 1048576)) МБ"
  elif [ -n "$mem" ]; then
    bad "памяти для Docker $((mem / 1048576)) МБ, нужно 4 ГБ" "Docker Desktop → Settings → Resources → Memory"
  fi

  free_kb="$(df -Pk "$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo .)" 2>/dev/null | awk 'NR==2 {print $4}')"
  [ -n "$free_kb" ] || free_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
  if [ -n "$free_kb" ] && [ "$free_kb" -ge 5242880 ] 2>/dev/null; then
    ok "место на диске: $((free_kb / 1048576)) ГБ свободно"
  elif [ -n "$free_kb" ]; then
    bad "на диске $((free_kb / 1024)) МБ свободно, нужно 5 ГБ" "освободите место: docker system prune"
  fi

  if [ -f .env ]; then
    ok ".env есть"
  else
    warn ".env нет" "make demo создаст его из .env.example; вручную: cp .env.example .env"
  fi
  check_secrets

  running="$(docker compose ps --status running -q 2>/dev/null)"
  http_port="$(env_value HTTP_PORT)"
  http_port="${http_port:-80}"
  if [ -n "$running" ]; then
    ok "стенд уже запущен: порты $http_port, 8010, 3010 и 8025 заняты им"
  else
    for port in "$http_port" 8010 3010 8025; do
      if port_busy "$port"; then
        if [ "$port" = "$http_port" ]; then
          bad "порт $port занят" "задайте в .env HTTP_PORT=8081 и PUBLIC_BASE_URL=http://localhost:8081"
        else
          bad "порт $port занят" "остановите процесс на этом порту (lsof -i :$port)"
        fi
      else
        ok "порт $port свободен"
      fi
    done
  fi

  while read -r image; do
    [ -n "$image" ] || continue
    # Keycloak runs only under the fsp-id profile (docs/INSTALL.md, 11.10).
    if [[ "$image" == *keycloak* ]] && [[ "${COMPOSE_PROFILES:-}$(env_value COMPOSE_PROFILES)" != *fsp-id* ]]; then
      continue
    fi
    if docker image inspect "$image" >/dev/null 2>&1; then
      ok "образ $image уже скачан"
    elif with_timeout 20 docker manifest inspect "$image" >/dev/null 2>&1; then
      ok "образ $image доступен в реестре"
    else
      bad "образ $image не скачан и реестр не отвечает" "проверьте сеть и прокси Docker (Settings → Resources → Proxies), затем docker pull $image"
    fi
  done < <(sed -n 's/^[[:space:]]*image:[[:space:]]*//p' docker-compose.yml | tr -d "\"'")
}

check_local() {
  local v
  if have python3.12; then
    ok "python3.12 $(first_version "$(python3.12 --version 2>&1)")"
  elif have python3 && ver_ge "$(first_version "$(python3 --version 2>&1)")" 3.12; then
    ok "python3 $(first_version "$(python3 --version 2>&1)")"
  else
    bad "Python 3.12 не найден" "установите Python 3.12 (python.org или uv python install 3.12)"
  fi

  v="$(first_version "$(node --version 2>/dev/null)")"
  if [ -n "$v" ] && ver_ge "$v" 20; then ok "node $v"; else bad "Node.js ${v:-не найден}: нужна версия 20 и новее" "https://nodejs.org/"; fi
  if have npm; then ok "npm $(npm --version 2>/dev/null)"; else bad "npm не найден" "ставится вместе с Node.js"; fi

  v="$(first_version "$(psql --version 2>/dev/null)")"
  if [ -n "$v" ] && ver_ge "$v" 16; then ok "psql $v"; else bad "PostgreSQL ${v:-не найден}: нужна версия 16 с pgvector" "установите PostgreSQL 16 и пакет pgvector"; fi
  if have pg_isready; then
    local db="${DATABASE_URL:-postgresql://fsp:fsp@localhost:5432/fsp_talent}"
    if pg_isready -q -d "${db/postgresql+asyncpg:/postgresql:}" 2>/dev/null || pg_isready -q -h localhost -p 5432; then
      ok "PostgreSQL принимает подключения"
    else
      bad "PostgreSQL не принимает подключения на localhost:5432" "запустите сервер: sudo systemctl start postgresql"
    fi
  fi

  v="$(first_version "$(redis-server --version 2>/dev/null || redis-cli --version 2>/dev/null)")"
  if [ -n "$v" ] && ver_ge "$v" 7; then ok "redis $v"; else bad "Redis ${v:-не найден}: нужна версия 7" "установите Redis 7"; fi
  if have redis-cli; then
    if [ "$(redis-cli -u "${REDIS_URL:-redis://localhost:6379/0}" ping 2>/dev/null)" = "PONG" ]; then
      ok "Redis отвечает на ping"
    else
      bad "Redis не отвечает на ${REDIS_URL:-redis://localhost:6379/0}" "запустите redis-server"
    fi
  fi

  # Defaults are the ones in backend/app/core/config.py.
  # Values are not printed: a URL can carry a password.
  if [ -n "${DATABASE_URL:-}" ]; then ok "DATABASE_URL задан"; else ok "DATABASE_URL не задан: по умолчанию fsp@localhost:5432/fsp_talent"; fi
  if [ -n "${REDIS_URL:-}" ]; then ok "REDIS_URL задан"; else ok "REDIS_URL не задан: по умолчанию localhost:6379/0"; fi
  ok "MAIL_MODE ${MAIL_MODE:-не задан: по умолчанию console, коды печатаются в журнал uvicorn}"
  check_secrets
}

if [ "${LOCAL:-}" = 1 ]; then
  echo "Проверка для запуска без Docker (docs/INSTALL.md, раздел 10)"
  check_local
else
  echo "Проверка перед make demo (docs/INSTALL.md, раздел 1)"
  check_docker
fi

echo
if [ "$FAILS" -gt 0 ]; then
  echo "Итог: ✗ $FAILS, предупреждений $WARNS. Исправьте строки с ✗ и запустите make doctor ещё раз."
  exit 1
fi
echo "Итог: всё готово, предупреждений $WARNS."

#!/bin/sh
set -e
mkdir -p /secrets
if id appuser >/dev/null 2>&1; then
  chown appuser:appuser /secrets
  if [ -f /secrets/vc_ed25519.pem ]; then
    chown appuser:appuser /secrets/vc_ed25519.pem
    chmod 600 /secrets/vc_ed25519.pem
  fi
  if [ "$(id -u)" = "0" ] && command -v runuser >/dev/null 2>&1; then
    # Preserve env (DATABASE_URL) but not root's home: asyncpg stats ~/.postgresql.
    export HOME=/home/appuser
    exec runuser -u appuser --preserve-environment -- "$@"
  fi
fi
exec "$@"

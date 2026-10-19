#!/bin/sh
# Dump the database to /backups and keep the newest 14 files.
set -eu
stamp=$(date +%Y%m%d-%H%M)
umask 077
pg_dump -h postgres -U fsp -d fsp_talent -Fc -f "/backups/fsp_talent-$stamp.dump"
chmod 600 "/backups/fsp_talent-$stamp.dump"
# The database dump cannot decrypt contacts or check old signatures without these keys.
if [ -d /secrets ]; then
  mkdir -p "/backups/keys-$stamp"
  cp -a /secrets/. "/backups/keys-$stamp/"
  chmod -R go-rwx "/backups/keys-$stamp"
  if [ -f /secrets/vc_ed25519.pem ] && [ ! -f "/backups/keys-$stamp/vc_ed25519.pem" ]; then
    echo "backup failed: signing key was not copied" >&2
    exit 1
  fi
fi
ls -1t /backups/fsp_talent-*.dump | tail -n +15 | xargs -r rm -f
if ls -1dt /backups/keys-* >/dev/null 2>&1; then
  ls -1dt /backups/keys-* | tail -n +15 | xargs -r rm -rf
fi
echo "backup ok: fsp_talent-$stamp.dump"

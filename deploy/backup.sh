#!/bin/sh
# Dump the database to /backups and keep the newest 14 files.
set -eu
stamp=$(date +%Y%m%d-%H%M)
pg_dump -h postgres -U fsp -d fsp_talent -Fc -f "/backups/fsp_talent-$stamp.dump"
ls -1t /backups/fsp_talent-*.dump | tail -n +15 | xargs -r rm -f
echo "backup ok: fsp_talent-$stamp.dump"

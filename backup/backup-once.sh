#!/bin/sh
# Take one compressed dump of the database into /backups and drop dumps older than 14 days.
set -eu

stamp=$(date +%Y%m%d_%H%M%S)
target="/backups/crm_${stamp}.dump"

pg_dump --format=custom --file="${target}.partial"
mv "${target}.partial" "${target}"
echo "$(date -Iseconds) backup written: ${target}"

find /backups -name 'crm_*.dump' -type f -mtime +13 -print -delete
find /backups -name 'crm_*.dump.partial' -type f -mmin +600 -delete

#!/bin/sh
# Run backup-once.sh every day at BACKUP_TIME (HH:MM, container local time = TZ).
set -eu

backup_time="${BACKUP_TIME:-02:00}"
echo "$(date -Iseconds) backup scheduler started, daily at ${backup_time}"

while true; do
    now=$(date +%s)
    next=$(date -d "today ${backup_time}" +%s)
    if [ "${next}" -le "${now}" ]; then
        next=$(date -d "tomorrow ${backup_time}" +%s)
    fi
    sleep $((next - now))
    /usr/local/bin/backup-once.sh || echo "$(date -Iseconds) backup FAILED" >&2
done

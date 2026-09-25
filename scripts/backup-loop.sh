#!/bin/sh
# Ежедневный pg_dump в час BACKUP_HOUR (UTC) и удаление архивов старше BACKUP_KEEP_DAYS дней.
set -eu
mkdir -p /backups
echo "[backup] сервис резервного копирования запущен, ежедневно в ${BACKUP_HOUR}:00 UTC, хранение ${BACKUP_KEEP_DAYS} дн."

do_backup() {
  ts=$(date -u +%Y%m%d_%H%M%S)
  file="/backups/crm_${ts}.dump"
  if pg_dump --format=custom --compress=9 --file="$file.tmp"; then
    mv "$file.tmp" "$file"
    echo "[backup] создан $file ($(du -h "$file" | cut -f1))"
  else
    rm -f "$file.tmp"
    echo "[backup] ОШИБКА резервного копирования" >&2
  fi
  find /backups -name 'crm_*.dump' -mtime +"${BACKUP_KEEP_DAYS}" -print -delete
}

# Первый архив — сразу после запуска, если за сегодня ещё нет
today=$(date -u +%Y%m%d)
ls /backups/crm_"${today}"_*.dump >/dev/null 2>&1 || do_backup

while true; do
  sleep 60
  if [ "$(date -u +%H:%M)" = "$(printf '%02d' "$BACKUP_HOUR"):00" ]; then
    do_backup
    sleep 60
  fi
done

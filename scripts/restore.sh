#!/bin/sh
# Восстановление БД из архива: ./scripts/restore.sh backups/crm_YYYYMMDD_HHMMSS.dump
# ВНИМАНИЕ: текущие данные БД будут заменены содержимым архива.
set -eu
cd "$(dirname "$0")/.."
file="${1:?Укажите файл архива: ./scripts/restore.sh backups/crm_....dump}"
[ -f "$file" ] || { echo "Файл $file не найден"; exit 1; }

start=$(date +%s)
echo "Останавливаю приложение..."
docker compose stop backend worker beat
echo "Восстанавливаю из $file..."
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < "$file"
echo "Запускаю приложение..."
docker compose start backend worker beat
echo "Восстановление завершено за $(( $(date +%s) - start )) сек."

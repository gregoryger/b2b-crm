#!/bin/sh
# Ручное резервное копирование: ./scripts/backup.sh
set -eu
cd "$(dirname "$0")/.."
ts=$(date -u +%Y%m%d_%H%M%S)
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --format=custom --compress=9 "$POSTGRES_DB"' > "backups/crm_${ts}.dump"
echo "Готово: backups/crm_${ts}.dump"

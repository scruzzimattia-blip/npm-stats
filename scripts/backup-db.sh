#!/bin/bash
# Backup script for NPM Monitor database settings and blocklists (excludes traffic table)

set -e

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="$BACKUP_DIR/npm_monitor_backup_$TIMESTAMP.sql"

echo "Starting backup to $FILENAME..."

# We use docker exec to run pg_dump. 
# We explicitly exclude the massive 'traffic' table and its partitions.
docker exec -e PGPASSWORD="$DB_PASSWORD" shared-postgres \
    pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --exclude-table-data=traffic \
    --exclude-table-data=traffic_default \
    --exclude-table-data='traffic_*' \
    -F c -f "/tmp/backup.dump"

docker cp shared-postgres:/tmp/backup.dump "$FILENAME"
docker exec shared-postgres rm /tmp/backup.dump

echo "Backup completed successfully."

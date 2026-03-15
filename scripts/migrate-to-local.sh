#!/bin/bash
# Migration script from Docker Postgres to Local Postgres

set -e

# Configuration (adjust as needed)
DOCKER_CONTAINER="shared-postgres"
DB_NAME="npm_monitor"
DB_USER="npm_user"
LOCAL_DB_USER="npm_user"
LOCAL_DB_NAME="npm_monitor"

echo "🐘 Migrating database from Docker to Local Postgres..."

# 1. Export from Docker
echo "📥 Dumping data from container $DOCKER_CONTAINER..."
docker exec -t $DOCKER_CONTAINER pg_dump -U $DB_USER $DB_NAME > npm_monitor_dump.sql

# 2. Prepare Local Postgres
echo "🛠️ Preparing local database..."
# Attempt to create user and db (requires sudo/postgres privileges)
sudo -u postgres psql -c "CREATE USER $LOCAL_DB_USER WITH PASSWORD 'YOUR_CHOSEN_PASSWORD';" || echo "User already exists"
sudo -u postgres psql -c "CREATE DATABASE $LOCAL_DB_NAME OWNER $LOCAL_DB_USER;" || echo "Database already exists"

# 3. Import to Local
echo "📤 Importing data to local Postgres..."
PGPASSWORD='YOUR_CHOSEN_PASSWORD' psql -h localhost -U $LOCAL_DB_USER -d $LOCAL_DB_NAME < npm_monitor_dump.sql

echo "✅ Migration complete!"
echo "⚠️  Remember to update your .env file with DB_HOST=localhost and your local password."
rm npm_monitor_dump.sql

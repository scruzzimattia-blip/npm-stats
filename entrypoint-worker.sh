#!/bin/bash
set -e

# Wait for DB to be ready and run migrations
echo "Running database migrations..."
uv run alembic upgrade head

# Start the background sync scheduler in foreground
echo "Starting NPM Log Sync Worker..."
exec python -m src.sync_scheduler

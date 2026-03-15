#!/bin/bash
set -e

# Wait for DB to be ready and run migrations
echo "Running database migrations..."
python -m alembic upgrade head

# Start the specialized log worker
echo "Starting specialized NPM Log Worker..."
exec python -m src.log_worker

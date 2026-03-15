#!/bin/bash
set -e

# Start the specialized cron worker
echo "Starting specialized NPM Cron Worker..."
exec python -m src.cron_worker

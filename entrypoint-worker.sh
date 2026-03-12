#!/bin/bash
set -e

# Start the background sync scheduler in foreground
echo "Starting NPM Log Sync Worker..."
exec python -m src.sync_scheduler

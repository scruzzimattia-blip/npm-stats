#!/bin/bash
set -e

# Start the background sync scheduler
echo "Starting background sync scheduler..."
python -m src.sync_scheduler &
SYNC_PID=$!

# Trap signals to forward to child processes
cleanup() {
    echo "Stopping services..."
    kill -TERM "$SYNC_PID" 2>/dev/null || true
    wait "$SYNC_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Start Streamlit in foreground
echo "Starting Streamlit..."
exec streamlit run run.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true

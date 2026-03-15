#!/bin/bash
set -e

# Start FastAPI server with uvicorn
echo "Starting NPM Monitor API..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8001

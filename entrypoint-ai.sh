#!/bin/bash
set -e

# Start the AI log analyzer in foreground
echo "Starting NPM AI Behavior Analyzer..."
exec python -m src.ai_analyzer

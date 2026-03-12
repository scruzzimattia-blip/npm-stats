#!/bin/bash
set -e

# Start Streamlit in foreground
echo "Starting Streamlit Dashboard..."
exec streamlit run run.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true

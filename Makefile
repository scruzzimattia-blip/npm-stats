# Makefile for managing standalone NPM Monitor applications

# Load environment variables from .env
ifneq (,$(wildcard .env))
    include .env
    export
endif

VENV = .venv
PYTHON = $(VENV)/bin/python3
STREAMLIT = $(VENV)/bin/streamlit
UVICORN = $(VENV)/bin/uvicorn

.PHONY: all help setup ui log-worker cron-worker ai api stop-all

setup:
	@echo "📦 Setting up virtual environment..."
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

help:
	@echo "Available commands:"
	@echo "  make ui           - Start the Streamlit Dashboard"
	@echo "  make log-worker   - Start the Real-time Log Sync Worker"
	@echo "  make cron-worker  - Start the Periodic Task Worker"
	@echo "  make ai           - Start the AI Behavior Analyzer"
	@echo "  make api          - Start the FastAPI Backend"
	@echo "  make stop-all     - Kill all running monitor processes"

ui:
	@echo "🚀 Starting UI..."
	$(STREAMLIT) run run.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true

log-worker:
	@echo "📜 Starting Log Worker..."
	$(PYTHON) -m src.log_worker

cron-worker:
	@echo "⏰ Starting Cron Worker..."
	$(PYTHON) -m src.cron_worker

ai:
	@echo "🤖 Starting AI Analyzer..."
	$(PYTHON) -m src.ai_analyzer

api:
	@echo "🔌 Starting API..."
	$(UVICORN) src.api.main:app --host 0.0.0.0 --port 8002

stop-all:
	@echo "🛑 Stopping all processes..."
	pkill -f "streamlit run run.py" || true
	pkill -f "python3 -m src.log_worker" || true
	pkill -f "python3 -m src.cron_worker" || true
	pkill -f "python3 -m src.ai_analyzer" || true
	pkill -f "uvicorn src.api.main:app" || true

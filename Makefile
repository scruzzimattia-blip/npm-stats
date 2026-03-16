# Makefile for managing standalone NPM Monitor applications

# Load environment variables from .env
ifneq (,$(wildcard .env))
    include .env
    export
endif

.PHONY: all help setup ui log-worker cron-worker ai api stop-all lint test

setup:
	@echo "📦 Setting up project with uv..."
	uv sync

help:
	@echo "Available commands:"
	@echo "  make setup        - Install dependencies with uv"
	@echo "  make ui           - Start the Streamlit Dashboard"
	@echo "  make log-worker   - Start the Real-time Log Sync Worker"
	@echo "  make cron-worker  - Start the Periodic Task Worker"
	@echo "  make ai           - Start the AI Behavior Analyzer"
	@echo "  make api          - Start the FastAPI Backend"
	@echo "  make lint         - Run ruff linter and formatter check"
	@echo "  make test         - Run pytest test suite"
	@echo "  make stop-all     - Kill all running monitor processes"

ui:
	@echo "🚀 Starting UI..."
	uv run streamlit run run.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true

log-worker:
	@echo "📜 Starting Log Worker..."
	uv run python -m src.log_worker

cron-worker:
	@echo "⏰ Starting Cron Worker..."
	uv run python -m src.cron_worker

ai:
	@echo "🤖 Starting AI Analyzer..."
	uv run python -m src.ai_analyzer

api:
	@echo "🔌 Starting API..."
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8002

lint:
	@echo "🔍 Running linter..."
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v

stop-all:
	@echo "🛑 Stopping all processes..."
	pkill -f "streamlit run run.py" || true
	pkill -f "python3 -m src.log_worker" || true
	pkill -f "python3 -m src.cron_worker" || true
	pkill -f "python3 -m src.ai_analyzer" || true
	pkill -f "uvicorn src.api.main:app" || true

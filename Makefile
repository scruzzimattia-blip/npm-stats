.PHONY: help install test lint format clean docker-build docker-run

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install dependencies using uv"
	@echo "  install-dev   - Install dev dependencies"
	@echo "  test          - Run all tests"
	@echo "  test-cov      - Run tests with coverage"
	@echo "  lint          - Run linting (ruff)"
	@echo "  format        - Format code (ruff)"
	@echo "  format-check  - Check code formatting"
	@echo "  clean         - Clean build artifacts"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"
	@echo "  docker-stop   - Stop Docker container"
	@echo "  sync          - Sync logs manually"
	@echo "  validate      - Validate configuration"

# Install dependencies
install:
	uv sync --frozen --no-dev

install-dev:
	uv sync --frozen

# Run tests
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Linting and formatting
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

format-check:
	uv run ruff format --check src/ tests/

# Clean build artifacts
clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf db-data
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-build:
	docker compose build

docker-run:
	docker compose up -d

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f npm-monitor

# Application commands
sync:
	uv run python -c "from src.sync import sync_logs; sync_logs()"

validate:
	uv run python -c "from src.config import validate_config_or_exit; validate_config_or_exit()"

# Development server
dev:
	uv run streamlit run src/app.py

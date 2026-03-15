FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install project dependencies
COPY pyproject.toml uv.lock .
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim

LABEL org.opencontainers.image.title="NPM Log Monitor"
LABEL org.opencontainers.image.description="Streamlit dashboard for analyzing Nginx Proxy Manager logs"
LABEL org.opencontainers.image.vendor="mattia"

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Ensure python uses the virtualenv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pages/ ./pages/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser run.py .
COPY --chown=appuser:appuser entrypoint.sh .
COPY --chown=appuser:appuser entrypoint-ui.sh .
COPY --chown=appuser:appuser entrypoint-worker.sh .
COPY --chown=appuser:appuser entrypoint-ai.sh .
COPY --chown=appuser:appuser entrypoint-api.sh .
COPY --chown=appuser:appuser entrypoint-log-worker.sh .
COPY --chown=appuser:appuser entrypoint-cron-worker.sh .
RUN chmod +x entrypoint.sh entrypoint-ui.sh entrypoint-worker.sh entrypoint-ai.sh entrypoint-api.sh entrypoint-log-worker.sh entrypoint-cron-worker.sh

USER appuser

EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["./entrypoint.sh"]

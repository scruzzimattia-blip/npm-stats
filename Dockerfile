FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install project dependencies
COPY pyproject.toml .
# We don't have uv.lock yet in the repo unless we run uv lock locally, but the lockfile will be created/used by uv sync
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

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
    iptables \
    sudo \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'appuser ALL=(ALL) NOPASSWD: /usr/sbin/iptables' >> /etc/sudoers

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Ensure python uses the virtualenv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser run.py .
COPY --chown=appuser:appuser entrypoint.sh .
RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["./entrypoint.sh"]

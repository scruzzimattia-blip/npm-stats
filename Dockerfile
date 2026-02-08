FROM python:3.12-slim

LABEL org.opencontainers.image.title="NPM Log Monitor"
LABEL org.opencontainers.image.description="Streamlit dashboard for analyzing Nginx Proxy Manager logs"
LABEL org.opencontainers.image.vendor="mattia"

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

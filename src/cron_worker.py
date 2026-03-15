#!/usr/bin/env python3
"""Periodic task worker for health checks and cleanup."""

import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import cleanup_old_data
from src.utils import setup_logging
from src.utils.npm_sync import check_all_hosts_health

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down cron-worker...")
    shutdown_requested = True

def run_cron_worker() -> None:
    """Run the periodic tasks loop."""
    setup_logging()
    logger.info("Starting specialized NPM Cron Worker (Periodic Tasks)")

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    cleanup_interval = int(os.getenv("CLEANUP_INTERVAL", "86400"))  # Default: 24h
    health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "300")) # Default: 5 min

    last_cleanup = 0 # Run cleanup on start
    last_health_check = 0 # Run health check on start

    while not shutdown_requested:
        now = time.time()

        # 1. Host health and SSL checks
        if now - last_health_check >= health_check_interval:
            logger.info("Cron: Starting host health and SSL check...")
            try:
                check_all_hosts_health()
                last_health_check = now
            except Exception as e:
                logger.error(f"Cron: Host health check error: {e}")

        # 2. Database cleanup and archiving
        if now - last_cleanup >= cleanup_interval:
            logger.info("Cron: Starting database cleanup...")
            try:
                deleted = cleanup_old_data()
                if deleted > 0:
                    logger.info(f"Cron: Cleaned up {deleted} old entries")
                last_cleanup = now
            except Exception as e:
                logger.error(f"Cron: Cleanup error: {e}")

        # Sleep a bit to avoid high CPU
        time.sleep(10)

    logger.info("Cron worker stopped")

if __name__ == "__main__":
    run_cron_worker()

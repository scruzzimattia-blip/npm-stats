#!/usr/bin/env python3
"""Background sync scheduler for NPM Monitor."""

import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import cleanup_old_data
from src.log_parser import init_geoip
from src.sync import sync_logs
from src.utils import setup_logging

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False


def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True


def run_scheduler() -> None:
    """Run the sync scheduler loop."""
    setup_logging()

    # Get sync interval from environment (default: 1 minute)
    sync_interval = int(os.getenv("SYNC_INTERVAL", "60"))
    cleanup_interval = int(os.getenv("CLEANUP_INTERVAL", "86400"))  # Default: 24h

    logger.info(f"Starting sync scheduler (interval: {sync_interval}s, cleanup: {cleanup_interval}s)")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initialize GeoIP
    init_geoip()

    last_cleanup = time.time()

    while not shutdown_requested:
        try:
            # Sync logs
            start = time.time()
            inserted = sync_logs()
            duration = time.time() - start

            if inserted > 0:
                logger.info(f"Synced {inserted} new entries in {duration:.2f}s")
            else:
                logger.debug(f"No new entries (check took {duration:.2f}s)")

            # Periodic cleanup
            if time.time() - last_cleanup > cleanup_interval:
                deleted = cleanup_old_data()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old entries")
                last_cleanup = time.time()

        except Exception as e:
            logger.error(f"Sync error: {e}")

        # Sleep in small increments to allow quick shutdown
        sleep_end = time.time() + sync_interval
        while time.time() < sleep_end and not shutdown_requested:
            time.sleep(1)

    logger.info("Sync scheduler stopped")


if __name__ == "__main__":
    run_scheduler()

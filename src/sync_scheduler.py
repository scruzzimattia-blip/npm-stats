#!/usr/bin/env python3
"""Background sync scheduler for NPM Monitor with Real-Time Streaming and Metrics."""

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from prometheus_client import Counter, Gauge, start_http_server
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import app_config
from src.database import cleanup_old_data
from src.log_parser import init_geoip
from src.sync import sync_logs
from src.utils import setup_logging
from src.utils.npm_sync import check_all_hosts_health

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

# Prometheus Metrics
METRIC_REQUESTS = Counter("npm_requests_total", "Total number of processed requests")
METRIC_BLOCKS = Counter("npm_blocks_total", "Total number of blocked IPs")
METRIC_SYNC_DUR = Gauge("npm_sync_duration_seconds", "Time spent in last sync")


def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True


class LogEventHandler(FileSystemEventHandler):
    """Event handler for log file modifications."""

    def __init__(self):
        self.sync_requested = threading.Event()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".log"):
            self.sync_requested.set()


def run_scheduler() -> None:
    """Run the real-time sync scheduler loop."""
    setup_logging()

    cleanup_interval = int(os.getenv("CLEANUP_INTERVAL", "86400"))  # Default: 24h

    logger.info(f"Starting real-time sync scheduler (cleanup: {cleanup_interval}s)")

    # Start Prometheus metrics server
    prometheus_port = int(os.getenv("PROMETHEUS_PORT", "8000"))
    try:
        start_http_server(prometheus_port)
        logger.info(f"Prometheus metrics server started on port {prometheus_port}")
    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 98:
            logger.warning(f"Prometheus port {prometheus_port} already in use, metrics disabled")
        else:
            logger.error(f"Failed to start Prometheus server: {e}")
    except Exception as e:
        logger.error(f"Failed to start Prometheus server: {e}")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initialize GeoIP
    init_geoip()

    # Setup Watchdog Observer
    event_handler = LogEventHandler()
    observer = Observer()
    log_dir = app_config.log_dir
    if os.path.exists(log_dir):
        observer.schedule(event_handler, log_dir, recursive=False)
        observer.start()
        logger.info(f"Started real-time log monitoring for directory: {log_dir}")
    else:
        logger.warning(f"Log directory {log_dir} does not exist. Falling back to periodic sync.")

    last_cleanup = time.time()
    last_health_check = time.time()
    health_check_interval = 300  # 5 minutes

    # Do an initial sync
    sync_logs()

    while not shutdown_requested:
        try:
            # Wait for changes, timeout every 1 second to check periodic tasks
            event_handler.sync_requested.wait(timeout=1.0)

            # If event was triggered or periodic fallback
            if event_handler.sync_requested.is_set() or not observer.is_alive():
                event_handler.sync_requested.clear()

                start = time.time()
                inserted = sync_logs()
                duration = time.time() - start

                METRIC_SYNC_DUR.set(duration)
                if inserted > 0:
                    METRIC_REQUESTS.inc(inserted)
                    logger.info(f"Real-time sync: {inserted} new entries in {duration:.2f}s")

            # Periodic host health check
            now = time.time()
            if now - last_health_check > health_check_interval:
                logger.info("Starting host health and SSL check...")
                try:
                    check_all_hosts_health()
                except Exception as e:
                    logger.error(f"Host health check error: {e}")
                last_health_check = now

            # Periodic cleanup
            if now - last_cleanup > cleanup_interval:
                deleted = cleanup_old_data()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old entries")
                last_cleanup = now

        except Exception as e:
            logger.error(f"Sync error: {e}")
            time.sleep(1)  # Prevent tight loop on crash

    if observer.is_alive():
        observer.stop()
        observer.join()

    logger.info("Sync scheduler stopped")


if __name__ == "__main__":
    run_scheduler()

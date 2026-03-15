#!/usr/bin/env python3
"""Real-time log monitoring worker."""

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
from src.log_parser import init_geoip
from src.sync import sync_logs
from src.utils import setup_logging

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

# Prometheus Metrics
METRIC_REQUESTS = Counter("npm_requests_total", "Total number of processed requests")
METRIC_SYNC_DUR = Gauge("npm_sync_duration_seconds", "Time spent in last sync")
METRIC_BLOCKED_IPS = Gauge("npm_blocked_ips_total", "Current number of blocked IPs")
METRIC_THREATS_DETECTED = Counter("npm_threats_detected_total", "Total number of security threats detected")


def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down log-worker...")
    shutdown_requested = True


class LogEventHandler(FileSystemEventHandler):
    """Event handler for log file modifications."""

    def __init__(self):
        self.sync_requested = threading.Event()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".log"):
            self.sync_requested.set()


def run_log_worker() -> None:
    """Run the real-time log monitoring loop."""
    setup_logging()
    logger.info("Starting specialized NPM Log Worker (Real-time)")

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

    # Register signal handlers
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
        logger.info(f"Monitoring log directory: {log_dir}")
    else:
        logger.warning(f"Log directory {log_dir} does not exist. Falling back to 60s periodic sync.")

    # Initial sync
    sync_logs()

    sync_interval = int(os.getenv("SYNC_INTERVAL", "60"))
    last_sync_time = time.time()

    while not shutdown_requested:
        try:
            # Wait for changes or periodic fallback
            # We want to sync at least every sync_interval seconds
            now = time.time()
            time_since_last_sync = now - last_sync_time
            wait_timeout = max(0.1, float(sync_interval) - time_since_last_sync)

            # If watchdog is alive, wait for its event with timeout
            if observer.is_alive():
                event_handler.sync_requested.wait(timeout=wait_timeout)
            else:
                time.sleep(wait_timeout)

            # Sync if event was triggered, or sync_interval passed, or observer died
            now = time.time()
            if (event_handler.sync_requested.is_set() or
                (now - last_sync_time >= sync_interval) or
                not observer.is_alive()):

                event_handler.sync_requested.clear()
                last_sync_time = now

                start = time.time()
                inserted = sync_logs()
                duration = time.time() - start

                METRIC_SYNC_DUR.set(duration)

                # Update Blocked IPs metric
                try:
                    from src.database import get_database_info
                    db_info = get_database_info()
                    METRIC_BLOCKED_IPS.set(db_info.get("blocked_count", 0))
                except Exception:
                    pass

                if inserted > 0:
                    METRIC_REQUESTS.inc(inserted)
                    logger.info(f"Processed {inserted} new log entries in {duration:.2f}s")
                elif not observer.is_alive():
                    # If observer is dead, we log every periodic sync for visibility
                    logger.debug("Periodic sync completed: 0 new entries")

        except Exception as e:
            logger.error(f"Log worker error: {e}")
            time.sleep(2)

    if observer.is_alive():
        observer.stop()
        observer.join()
    logger.info("Log worker stopped")


if __name__ == "__main__":
    run_log_worker()

"""Shared log synchronization logic for NPM Monitor."""

import logging
from datetime import datetime
from typing import Optional

from .blocking import get_blocker
from .config import app_config
from .database import (
    cleanup_expired_blocks,
    get_newest_timestamp,
    init_database,
    insert_traffic_batch,
)
from .log_parser import parse_all_logs

logger = logging.getLogger(__name__)


def sync_logs(since: Optional[datetime] = None) -> int:
    """Synchronize logs to database, only importing new entries."""
    init_database()

    # Cleanup expired blocks once in a while
    try:
        cleanup_expired_blocks()
    except Exception as e:
        logger.error(f"Error cleaning up expired blocks: {e}")

    effective_since = since if since is not None else get_newest_timestamp()
    rows = parse_all_logs(since=effective_since)

    if not rows:
        return 0

    # Check for blocking if enabled
    if app_config.enable_blocking:
        blocker = get_blocker(use_firewall=app_config.use_firewall)

        # Process each row for blocking/telemetry
        blocked_ips = set()
        for row in rows:
            ip = row[5] if len(row) > 5 else None
            status = row[4] if len(row) > 4 else None
            path = row[3] if len(row) > 3 else ""
            host = row[1] if len(row) > 1 else ""
            ua = row[6] if len(row) > 6 else ""
            country = row[9] if len(row) > 9 else ""

            if ip and status:
                if ip in blocked_ips:
                    continue

                # Check if IP is already locally cached as blocked
                if blocker.is_blocked(ip):
                    blocked_ips.add(ip)
                    continue

                try:
                    # Update counters and check for blocks for EVERY request
                    reason = blocker.check_request(
                        ip, status, path, host, ua, country
                    )
                    if reason:
                        blocked_ips.add(ip)
                except Exception as e:
                    logger.error(f"Error checking IP {ip}: {e}")

    inserted = insert_traffic_batch(rows)
    logger.info("Synced %d new entries", inserted)
    return inserted

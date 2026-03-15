"""Shared log synchronization logic for NPM Monitor."""

import logging
from collections import defaultdict
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

    # Check for blocking if enabled - optimized batch processing
    if app_config.enable_blocking:
        blocker = get_blocker(use_firewall=app_config.use_firewall)

        # Group rows by IP for efficient processing
        ip_requests = defaultdict(list)
        for row in rows:
            ip = row[5] if len(row) > 5 else None
            if ip:
                ip_requests[ip].append(row)

        # Get unique IPs to check
        unique_ips = list(ip_requests.keys())
        blocked_ips = set()

        # Filter to only check IPs that aren't already blocked
        ips_to_check = [ip for ip in unique_ips if not blocker.is_blocked(ip)]

        # Process each unique IP only once
        for ip in ips_to_check:
            try:
                # Get first request for this IP as sample
                sample_row = ip_requests[ip][0]
                status = sample_row[4] if len(sample_row) > 4 else None
                path = sample_row[3] if len(sample_row) > 3 else ""
                host = sample_row[1] if len(sample_row) > 1 else ""
                ua = sample_row[6] if len(sample_row) > 6 else ""
                country = sample_row[9] if len(sample_row) > 9 else ""

                # Process all requests for this IP to update counters
                for row in ip_requests[ip]:
                    status = row[4] if len(row) > 4 else None
                    path = row[3] if len(row) > 3 else ""
                    host = row[1] if len(row) > 1 else ""
                    ua = row[6] if len(row) > 6 else ""
                    country = row[9] if len(row) > 9 else ""

                    if status:
                        reason = blocker.check_request(ip, status, path, host, ua, country)
                        if reason and ip not in blocked_ips:
                            blocked_ips.add(ip)
                            break  # Stop checking once blocked
            except Exception as e:
                logger.error(f"Error checking IP {ip}: {e}")

    inserted = insert_traffic_batch(rows)
    logger.info("Synced %d new entries", inserted)
    return inserted

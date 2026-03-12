"""Shared log synchronization logic for NPM Monitor."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .blocking import get_blocker
from .config import app_config
from .database import (
    add_blocked_ip,
    cleanup_expired_blocks,
    get_newest_timestamp,
    init_database,
    insert_traffic_batch,
)
from .log_parser import parse_all_logs

logger = logging.getLogger(__name__)


def sync_logs(since: Optional[datetime] = None) -> int:
    """Synchronize logs to database, only importing new entries.

    If *since* is provided, only entries newer than that timestamp are considered.
    When *since* is None, the newest timestamp from the database is used.
    """
    init_database()

    # Cleanup expired blocks
    try:
        expired = cleanup_expired_blocks()
        if expired > 0:
            logger.info(f"Cleaned up {expired} expired blocks")
    except Exception as e:
        logger.error(f"Error cleaning up expired blocks: {e}")

    effective_since = since if since is not None else get_newest_timestamp()
    rows = parse_all_logs(since=effective_since)

    # Check for blocking if enabled
    blocked_ips = {}
    if app_config.enable_blocking:
        blocker = get_blocker(use_firewall=app_config.use_firewall)
        blocked_count = 0

        for row in rows:
            ip = row[5] if len(row) > 5 else None  # remote_addr
            status = row[4] if len(row) > 4 else None  # status
            path = row[3] if len(row) > 3 else None  # path
            host = row[1] if len(row) > 1 else None  # host

            if ip and status:
                reason = blocker.check_request(ip, status, path or "", host or "")
                if reason and ip not in blocked_ips:
                    blocked_ips[ip] = reason
                    blocked_count += 1

        # Store blocked IPs in database
        for ip, reason in blocked_ips.items():
            try:
                block_until = datetime.now(timezone.utc) + timedelta(seconds=app_config.block_duration)
                add_blocked_ip(ip, reason, block_until, is_manual=False)
                logger.warning(f"Auto-blocked IP {ip}: {reason}")
            except Exception as e:
                logger.error(f"Error blocking IP {ip}: {e}")

        if blocked_count > 0:
            logger.info(f"Auto-blocked {blocked_count} IPs due to suspicious activity")

    inserted = insert_traffic_batch(rows)

    logger.info("Synced %d new entries", inserted)
    return inserted

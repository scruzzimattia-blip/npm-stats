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


from collections import defaultdict

def sync_logs(since: Optional[datetime] = None) -> int:
    """Synchronize logs to database, only importing new entries."""
    # Database is initialized lazily or by the caller, 
    # but we do a health check to ensure connectivity.
    
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
        
        # Aggregate failures per IP in this batch to reduce DB calls
        ip_stats = defaultdict(lambda: {"404": 0, "403": 0, "5xx": 0, "suspicious": 0, "failed": 0, "last_path": "", "last_host": ""})
        
        for row in rows:
            ip = row[5] if len(row) > 5 else None
            status = row[4] if len(row) > 4 else None
            path = row[3] if len(row) > 3 else ""
            host = row[1] if len(row) > 1 else ""

            if ip and status:
                is_suspicious = blocker._is_suspicious_path(path)
                is_404 = 1 if status == 404 else 0
                is_403 = 1 if status == 403 else 0
                is_5xx = 1 if 500 <= status <= 599 else 0
                is_failed = 1 if (is_404 or is_403 or is_5xx or is_suspicious) else 0
                
                s = ip_stats[ip]
                s["404"] += is_404
                s["403"] += is_403
                s["5xx"] += is_5xx
                s["suspicious"] += 1 if is_suspicious else 0
                s["failed"] += is_failed
                s["last_path"] = path
                s["last_host"] = host

        # Update DB only once per IP found in batch
        blocked_count = 0
        for ip, stats in ip_stats.items():
            if stats["failed"] > 0:
                # If IP is already locally cached as blocked, skip
                if blocker.is_blocked(ip):
                    continue
                    
                try:
                    # In this optimized version, we could have a batch-update for counters,
                    # but for now we just call it once with the aggregated counts.
                    # Note: update_request_counters needs to be updated to support increments > 1
                    # For now, we still use the single update logic but it's already much better.
                    reason = blocker.check_request(ip, 0, stats["last_path"], stats["last_host"])
                    if reason:
                        blocked_count += 1
                except Exception as e:
                    logger.error(f"Error checking IP {ip}: {e}")

    inserted = insert_traffic_batch(rows)
    logger.info("Synced %d new entries", inserted)
    return inserted

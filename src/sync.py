"""Shared log synchronization logic for NPM Monitor."""

import logging
from datetime import datetime
from typing import Optional

from .database import get_newest_timestamp, init_database, insert_traffic_batch
from .log_parser import parse_all_logs

logger = logging.getLogger(__name__)


def sync_logs(since: Optional[datetime] = None) -> int:
    """Synchronize logs to database, only importing new entries.

    If *since* is provided, only entries newer than that timestamp are considered.
    When *since* is None, the newest timestamp from the database is used.
    """
    init_database()

    effective_since = since if since is not None else get_newest_timestamp()
    rows = parse_all_logs(since=effective_since)
    inserted = insert_traffic_batch(rows)

    logger.info("Synced %d new entries", inserted)
    return inserted

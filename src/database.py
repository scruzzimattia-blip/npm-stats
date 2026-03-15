"""Database operations for NPM Monitor."""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import pandas as pd
import redis
from psycopg import Connection
from psycopg import rows as psycopg_rows
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import app_config, db_config

logger = logging.getLogger(__name__)

# Connection pool (initialized lazily)
_pool: Optional[ConnectionPool] = None
_engine: Optional[Engine] = None
_db_available: bool = False

# Query timeout in seconds
QUERY_TIMEOUT = 30


def is_database_available() -> bool:
    """Check if database is reachable."""
    global _db_available
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        _db_available = True
        return True
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        _db_available = False
        return False


def get_pool() -> ConnectionPool:
    """Get or create the optimized connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=db_config.psycopg_connection_string,
            min_size=db_config.pool_min_conn,
            max_size=db_config.pool_max_conn,
            open=True,
            # Performance optimizations
            timeout=10,  # Connection timeout
            max_idle=300,  # Max idle time before closing
            max_lifetime=3600,  # Max connection lifetime
        )
        logger.info(f"Connection pool created (min={db_config.pool_min_conn}, max={db_config.pool_max_conn})")
    return _pool


def get_engine() -> Engine:
    """Get or create SQLAlchemy engine for pandas compatibility."""
    global _engine
    if _engine is None:
        _engine = create_engine(db_config.connection_string)
    return _engine


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """Context manager for database connections from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '30s'")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise


def init_database() -> bool:
    """Initialize database schema via Alembic (handled externally or in entrypoints)."""
    logger.info("Database schema is now managed by Alembic. Assuming up-to-date schema.")
    return True


def get_ai_reports(ip_address: str) -> List[Dict[str, Any]]:
    """Get all AI analysis reports for a specific IP."""
    query = """
        SELECT report, threat_level, model, analyzed_at
        FROM ai_analysis
        WHERE ip_address = %s
        ORDER BY analyzed_at DESC;
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query, (ip_address,))
            return cur.fetchall()


def add_ai_report(ip_address: str, report: str, threat_level: str, model: str) -> bool:
    """Save a new AI analysis report to the database."""
    query = """
        INSERT INTO ai_analysis (ip_address, report, threat_level, model)
        VALUES (%s, %s, %s, %s);
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (ip_address, report, threat_level, model))
            return True
    except Exception as e:
        logger.error(f"Failed to save AI report for {ip_address}: {e}")
        return False


def get_asn_blocklist() -> List[Dict[str, Any]]:
    """Get all blocked ASNs."""
    query = "SELECT asn, description, blocked_at, reason FROM asn_blocklist ORDER BY blocked_at DESC"
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query)
            return cur.fetchall()


def add_asn_block(asn: str, description: str, reason: str = "Manuelle Sperre") -> bool:
    """Add an ASN to the blocklist."""
    query = """
        INSERT INTO asn_blocklist (asn, description, reason)
        VALUES (%s, %s, %s)
        ON CONFLICT (asn) DO UPDATE SET reason = EXCLUDED.reason;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (str(asn), description, reason))
            return True
    except Exception as e:
        logger.error(f"Failed to block ASN {asn}: {e}")
        return False


def remove_asn_block(asn: str) -> bool:
    """Remove an ASN from the blocklist."""
    query = "DELETE FROM asn_blocklist WHERE asn = %s"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (str(asn),))
            return True
    except Exception as e:
        logger.error(f"Failed to remove ASN block {asn}: {e}")
        return False


def update_host_health(host: str, is_up: bool, status_code: int, ssl_expiry: Optional[datetime], response_time: float):
    """Update health status for a host."""
    query = """
        INSERT INTO host_health (host, is_up, status_code, ssl_expiry, response_time, last_check)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (host) DO UPDATE SET
            is_up = EXCLUDED.is_up,
            status_code = EXCLUDED.status_code,
            ssl_expiry = EXCLUDED.ssl_expiry,
            response_time = EXCLUDED.response_time,
            last_check = NOW();
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (host, is_up, status_code, ssl_expiry, response_time))
            return True
    except Exception as e:
        logger.error(f"Failed to update health for {host}: {e}")
        return False


def get_all_host_health() -> List[Dict[str, Any]]:
    """Get health status for all hosts."""
    query = "SELECT * FROM host_health ORDER BY host ASC"
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query)
            return cur.fetchall()


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    query = "SELECT id, username, password_hash, role, created_at, totp_secret FROM users WHERE username = %s"
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query, (username,))
            return cur.fetchone()


def create_user(username: str, password_hash: str, role: str = "viewer", totp_secret: Optional[str] = None) -> bool:
    """Create a new user."""
    query = "INSERT INTO users (username, password_hash, role, totp_secret) VALUES (%s, %s, %s, %s)"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (username, password_hash, role, totp_secret))
            return True
    except Exception as e:
        logger.error(f"Failed to create user {username}: {e}")
        return False


def update_user_totp_secret(username: str, totp_secret: Optional[str]) -> bool:
    """Update TOTP secret for a user."""
    query = "UPDATE users SET totp_secret = %s WHERE username = %s"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (totp_secret, username))
            return True
    except Exception as e:
        logger.error(f"Failed to update TOTP secret for {username}: {e}")
        return False


def list_users() -> List[Dict[str, Any]]:
    """List all registered users."""
    query = "SELECT id, username, role, created_at FROM users"
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query)
            return cur.fetchall()


def insert_traffic_batch(rows: List[Tuple]) -> int:
    """Insert traffic records in batch using COPY (much faster than executemany)."""
    if not rows:
        return 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            copy_sql = (
                "COPY traffic (time, host, method, path, status, remote_addr, "
                "user_agent, referer, response_length, country_code, city, "
                "scheme, latitude, longitude) FROM STDIN"
            )
            with cur.copy(copy_sql) as copy:
                for row in rows:
                    copy.write_row(row)
            return len(rows)


# Initialize Redis client lazily
_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(app_config.redis_url, decode_responses=True)
    return _redis_client


# Request tracker operations for shared blocking state (Now using Redis)
def update_request_counters(ip: str, status: int, is_suspicious: bool = False) -> Dict[str, int]:
    """Update request counters in Redis and return current counts."""
    r = get_redis()
    key = f"tracker:{ip}"

    is_404 = 1 if status == 404 else 0
    is_403 = 1 if status == 403 else 0
    is_5xx = 1 if 500 <= status <= 599 else 0
    is_susp = 1 if is_suspicious else 0
    is_failed = 1 if (is_404 or is_403 or is_5xx or is_susp) else 0

    # Use Redis pipeline for atomic operations
    import time

    pipe = r.pipeline()
    pipe.hincrby(key, "count_404", is_404)
    pipe.hincrby(key, "count_403", is_403)
    pipe.hincrby(key, "count_5xx", is_5xx)
    pipe.hincrby(key, "count_suspicious", is_susp)
    pipe.hincrby(key, "total_failed", is_failed)
    pipe.hincrby(key, "total_requests", 1)

    # Update threat score
    threat_increment = 0
    if is_susp:
        threat_increment += 30
    elif is_403:
        threat_increment += 20
    elif is_404:
        threat_increment += 5
    elif is_5xx:
        threat_increment += 10

    if threat_increment > 0:
        pipe.hincrby(key, "threat_score", threat_increment)
        pipe.hset(key, "last_update_ts", time.time())

    # Set TTL to 24h for long-term tracking
    pipe.expire(key, 86400)

    pipe.execute()

    # Build result dict
    current_data = r.hgetall(key)
    return {
        "count_404": int(current_data.get("count_404", 0)),
        "count_403": int(current_data.get("count_403", 0)),
        "count_5xx": int(current_data.get("count_5xx", 0)),
        "count_suspicious": int(current_data.get("count_suspicious", 0)),
        "total_failed": int(current_data.get("total_failed", 0)),
        "total_requests": int(current_data.get("total_requests", 0)),
        "threat_score": int(current_data.get("threat_score", 0)),
    }


def get_threat_score(ip: str) -> int:
    """Get current threat score for an IP with decay (-10 per hour)."""
    r = get_redis()
    key = f"tracker:{ip}"
    data = r.hgetall(key)
    if not data:
        return 0

    score = int(data.get("threat_score", 0))
    last_update = float(data.get("last_update_ts", 0))

    if score > 0 and last_update > 0:
        import time

        hours_passed = (time.time() - last_update) / 3600
        decay = int(hours_passed * 10)
        if decay > 0:
            score = max(0, score - decay)
            r.hset(key, "threat_score", score)

    return score


def update_threat_score(ip: str, increment: int):
    """Update threat score manually (e.g. for instant blocks)."""
    r = get_redis()
    key = f"tracker:{ip}"
    import time

    pipe = r.pipeline()
    pipe.hincrby(key, "threat_score", increment)
    pipe.hset(key, "last_update_ts", time.time())
    pipe.execute()


def reset_request_counters(ip: str):
    """Reset counters for an IP after blocking."""
    try:
        get_redis().delete(f"tracker:{ip}")
    except Exception as e:
        logger.error(f"Failed to reset Redis counter for {ip}: {e}")


def cleanup_trackers(max_age_minutes: int = 60):
    """Redis handles cleanup automatically via TTL. This is a no-op."""
    pass


def get_tracked_ip_count() -> int:
    """Get the number of IPs currently being tracked for suspicious activity from Redis."""
    try:
        # Avoid keys '*' in prod, but scan is safer. Counting keys is O(N).
        # We can just return an approximation or 0 if not critical.
        return len(get_redis().keys("tracker:*"))
    except Exception:
        return 0


def cleanup_old_data(days: Optional[int] = None) -> int:
    """Archive old data to CSV and delete from DB. Returns number of deleted rows."""
    retention_days = days if days is not None else app_config.retention_days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    archive_dir = Path("archives")
    archive_dir.mkdir(exist_ok=True)

    archive_file = archive_dir / f"traffic_archive_{cutoff_date.strftime('%Y%m%d')}.csv.gz"

    with get_connection() as conn:
        # 1. Export to CSV before deletion
        try:
            query = "SELECT * FROM traffic WHERE time < %s"
            df = pd.read_sql(query, get_engine(), params=(cutoff_date,))
            if not df.empty:
                df.to_csv(archive_file, index=False, compression="gzip")
                logger.info(f"Archived {len(df)} rows to {archive_file}")
        except Exception as e:
            logger.error(f"Failed to archive data: {e}")

        # 2. Perform deletion
        with conn.cursor() as cur:
            cur.execute("DELETE FROM traffic WHERE time < %s", (cutoff_date,))
            deleted = cur.rowcount
            logger.info(f"Cleaned up {deleted} rows older than {retention_days} days")
            return deleted


def get_newest_timestamp() -> Optional[datetime]:
    """Get the newest record timestamp from the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(time) FROM traffic;")
            result = cur.fetchone()
            return result[0] if result else None


def load_traffic_df(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50000,
    offset: int = 0,
) -> pd.DataFrame:
    """Load traffic data from database as DataFrame using SQLAlchemy with pagination."""
    conditions = []
    params: dict = {}

    if hosts:
        conditions.append("host = ANY(:hosts)")
        params["hosts"] = list(hosts)
    if start_date:
        conditions.append("time >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("time <= :end_date")
        params["end_date"] = end_date

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params["limit"] = limit
    params["offset"] = offset

    query = f"""
        SELECT time, host, method, path, status, remote_addr,
               user_agent, referer, response_length, country_code, city, latitude, longitude
        FROM traffic
        {where_clause}
        ORDER BY time DESC
        LIMIT :limit OFFSET :offset;
    """

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
        # Ensure time column is datetime
        if not df.empty and "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
    return df


def get_latest_logs(limit: int = 20) -> pd.DataFrame:
    """Convenience function to get the most recent traffic logs."""
    return load_traffic_df(limit=limit)


def get_traffic_count(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> int:
    """Get total count of traffic records matching filters."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(list(hosts))
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM traffic {where_clause};",
                params or None,
            )
            return cur.fetchone()[0]


def get_traffic_metrics(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get aggregated traffic metrics directly from DB."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(list(hosts))
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT
            COUNT(*) as total_requests,
            COUNT(DISTINCT remote_addr) as unique_ips,
            SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as error_count,
            SUM(response_length) as total_bytes
        FROM traffic
        {where_clause};
    """

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query, params or None)
            res = cur.fetchone()
            return {
                "total_requests": res["total_requests"] or 0,
                "unique_ips": res["unique_ips"] or 0,
                "error_count": res["error_count"] or 0,
                "total_bytes": res["total_bytes"] or 0,
            }


def get_hourly_traffic_summary(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """Get hourly traffic summary for charts."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(list(hosts))
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    DATE_TRUNC('hour', time) as hour,
                    COUNT(*) as request_count,
                    COUNT(DISTINCT remote_addr) as unique_ips,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as error_count,
                    SUM(response_length) as total_bytes
                FROM traffic
                {where_clause}
                GROUP BY DATE_TRUNC('hour', time)
                ORDER BY hour DESC;
                """,
                params or None,
            )
            rows = cur.fetchall()
            return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_top_ips_summary(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Get top IPs summary (aggregated)."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(list(hosts))
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    remote_addr,
                    COUNT(*) as request_count,
                    COUNT(DISTINCT host) as hosts_accessed,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as error_count,
                    SUM(response_length) as total_bytes,
                    MAX(time) as last_seen
                FROM traffic
                {where_clause}
                GROUP BY remote_addr
                ORDER BY request_count DESC
                LIMIT %s;
                """,
                params + [limit] if params else [limit],
            )
            rows = cur.fetchall()
            return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_geo_summary(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, pd.DataFrame]:
    """Get optimized geographic aggregations directly from the database."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(list(hosts))
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            # Get country stats
            cur.execute(
                f"""
                SELECT
                    country_code,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as error_count
                FROM traffic
                {where_clause} AND country_code IS NOT NULL
                GROUP BY country_code
                ORDER BY request_count DESC
                LIMIT 50;
                """,
                params or None,
            )
            country_rows = cur.fetchall()

            # Get city stats
            cur.execute(
                f"""
                SELECT
                    city,
                    COUNT(*) as request_count
                FROM traffic
                {where_clause} AND city IS NOT NULL
                GROUP BY city
                ORDER BY request_count DESC
                LIMIT 50;
                """,
                params or None,
            )
            city_rows = cur.fetchall()

            return {
                "countries": pd.DataFrame(country_rows) if country_rows else pd.DataFrame(),
                "cities": pd.DataFrame(city_rows) if city_rows else pd.DataFrame(),
            }


# Blocklist operations
def add_blocked_ip(ip_address: str, reason: str, block_until: datetime, is_manual: bool = False) -> bool:
    """Add an IP address to the blocklist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO blocklist (ip_address, reason, block_until, is_manual)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ip_address) DO UPDATE
                SET reason = EXCLUDED.reason,
                    block_until = EXCLUDED.block_until,
                    is_manual = EXCLUDED.is_manual,
                    unblocked_at = NULL;
                """,
                (ip_address, reason, block_until, is_manual),
            )
            return True


def remove_blocked_ip(ip_address: str) -> bool:
    """Remove an IP address from the blocklist (soft delete by setting unblocked_at)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE blocklist SET unblocked_at = NOW() WHERE ip_address = %s;",
                (ip_address,),
            )
            return True


def unblock_ip(ip_address: str) -> bool:
    """Alias for remove_blocked_ip for better naming consistency."""
    return remove_blocked_ip(ip_address)


def get_blocked_ips(active_only: bool = True) -> List[Tuple]:
    """Get all blocked IPs from the database."""
    query = "SELECT ip_address, reason, blocked_at, block_until, is_manual FROM blocklist"
    if active_only:
        query += " WHERE unblocked_at IS NULL AND block_until > NOW()"
    query += " ORDER BY blocked_at DESC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def get_blocklist_with_ai_status() -> List[Dict[str, Any]]:
    """Get the active blocklist with AI analysis status."""
    query = """
        SELECT
            b.ip_address, b.reason, b.blocked_at, b.block_until, b.is_manual,
            (SELECT COUNT(*) FROM ai_analysis a WHERE a.ip_address = b.ip_address) as ai_report_count
        FROM blocklist b
        WHERE b.block_until > NOW() AND b.unblocked_at IS NULL
        ORDER BY b.blocked_at DESC;
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query)
            return cur.fetchall()


# Whitelist operations
def get_whitelist() -> List[Dict[str, Any]]:
    """Get all whitelisted IPs from the database."""
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute("SELECT ip_address, reason, added_at FROM whitelist ORDER BY added_at DESC;")
            return cur.fetchall()


def add_to_whitelist(ip_address: str, reason: str = "Manual whitelist") -> bool:
    """Add an IP address to the whitelist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whitelist (ip_address, reason, added_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (ip_address) DO UPDATE
                SET reason = EXCLUDED.reason,
                    added_at = NOW();
                """,
                (ip_address, reason),
            )
            # Also remove from blocklist if present
            cur.execute(
                "UPDATE blocklist SET unblocked_at = NOW() WHERE ip_address = %s AND unblocked_at IS NULL;",
                (ip_address,),
            )
            return True


def remove_from_whitelist(ip_address: str) -> bool:
    """Remove an IP address from the whitelist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM whitelist WHERE ip_address = %s;", (ip_address,))
            return True


def cleanup_expired_blocks() -> int:
    """Cleanup expired blocks from the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE blocklist SET unblocked_at = NOW() WHERE unblocked_at IS NULL AND block_until <= NOW();"
            )
            return cur.rowcount


def get_distinct_hosts() -> List[str]:
    """Get list of distinct hosts from the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT host FROM traffic ORDER BY host;")
            return [row[0] for row in cur.fetchall()]


def get_database_info() -> Dict[str, Any]:
    """Get database statistics and information."""
    info = {
        "total_rows": 0,
        "blocked_count": 0,
        "table_size": "0 B",
        "oldest_record": None,
        "newest_record": None,
    }
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Row counts
                cur.execute("SELECT COUNT(*) FROM traffic;")
                info["total_rows"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM blocklist WHERE unblocked_at IS NULL AND block_until > NOW();")
                info["blocked_count"] = cur.fetchone()[0]

                # Table size (traffic only, as it's the main data)
                cur.execute("SELECT pg_size_pretty(pg_total_relation_size('traffic'));")
                info["table_size"] = cur.fetchone()[0]

                # Timestamps
                cur.execute("SELECT MIN(time), MAX(time) FROM traffic;")
                res = cur.fetchone()
                if res and res[0]:
                    info["oldest_record"] = res[0]
                    info["newest_record"] = res[1]
    except Exception as e:
        logger.error(f"Error getting database info: {e}")

    return info


def get_traffic_spike_metrics(
    hosts: Optional[List[str]] = None, recent_minutes: int = 5, baseline_minutes: int = 60
) -> Dict[str, Any]:
    """
    Compare recent traffic with a baseline to detect spikes.

    Returns:
        Dict with current_rate, baseline_rate, and is_spike boolean.
    """
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(minutes=recent_minutes)
    baseline_start = now - timedelta(minutes=baseline_minutes)

    conditions = []
    params: Dict[str, Any] = {"recent_start": recent_start, "baseline_start": baseline_start}

    if hosts:
        conditions.append("host = ANY(%(hosts)s)")
        params["hosts"] = list(hosts)

    where_clause = " AND ".join(conditions) + " AND " if conditions else ""

    query = f"""
        SELECT
            SUM(CASE WHEN time >= %(recent_start)s THEN 1 ELSE 0 END) as recent_count,
            COUNT(*) as baseline_count
        FROM traffic
        WHERE {where_clause} time >= %(baseline_start)s;
    """

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            cur.execute(query, params)
            res = cur.fetchone()

            recent_count = res["recent_count"] or 0
            baseline_count = res["baseline_count"] or 0

            # Calculate rates per minute
            current_rate = recent_count / recent_minutes
            # Baseline rate (excluding the recent window to be more accurate)
            baseline_rate = (baseline_count - recent_count) / max(1, (baseline_minutes - recent_minutes))

            return {
                "current_rate": round(current_rate, 2),
                "baseline_rate": round(baseline_rate, 2),
                "recent_count": recent_count,
                "is_spike": (
                    recent_count >= app_config.spike_min_requests
                    and current_rate > (baseline_rate * app_config.spike_threshold_factor)
                )
                if app_config.enable_anomaly_detection
                else False,
            }


def health_check() -> bool:
    """Check if database is healthy."""
    return is_database_available()


# Settings operations
def get_all_settings() -> Dict[str, str]:
    """Get all settings from the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings;")
            return {row[0]: row[1] for row in cur.fetchall()}


def update_setting(key: str, value: Any) -> bool:
    """Update or insert a setting in the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = NOW();
                """,
                (key, str(value)),
            )
            return True

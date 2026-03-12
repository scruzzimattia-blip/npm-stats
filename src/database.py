"""Database operations for NPM Monitor."""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

import pandas as pd
import psycopg
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
    """Initialize database schema with optimized indexes. Returns True if successful."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Main traffic table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS traffic (
                        id SERIAL PRIMARY KEY,
                        time TIMESTAMPTZ NOT NULL,
                        host TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        status INTEGER NOT NULL,
                        remote_addr TEXT NOT NULL,
                        user_agent TEXT
                    );
                """)

                # Add new columns if they don't exist
                new_columns = [
                    ("referer", "TEXT"),
                    ("response_length", "BIGINT"),
                    ("country_code", "CHAR(2)"),
                    ("city", "TEXT"),
                    ("scheme", "TEXT"),
                    ("latitude", "DOUBLE PRECISION"),
                    ("longitude", "DOUBLE PRECISION"),
                ]

                for col_name, col_type in new_columns:
                    cur.execute(f"""
                        DO $$
                        BEGIN
                            ALTER TABLE traffic ADD COLUMN {col_name} {col_type};
                        EXCEPTION
                            WHEN duplicate_column THEN
                                NULL;
                        END $$;
                    """)

                # Migration: change response_length from INTEGER to BIGINT if needed
                cur.execute("""
                    DO $$
                    BEGIN
                        ALTER TABLE traffic ALTER COLUMN response_length TYPE BIGINT;
                    EXCEPTION
                        WHEN others THEN
                            NULL;
                    END $$;
                """)
                # Create basic indexes
                indexes = [
                    ("idx_traffic_time", "traffic (time DESC)"),
                    ("idx_traffic_host", "traffic (host)"),
                    ("idx_traffic_remote_addr", "traffic (remote_addr)"),
                    ("idx_traffic_status", "traffic (status)"),
                    ("idx_traffic_time_host", "traffic (time DESC, host)"),
                    ("idx_traffic_country", "traffic (country_code)"),
                    # Additional composite indexes for common query patterns
                    ("idx_traffic_host_status", "traffic (host, status)"),
                    ("idx_traffic_time_status", "traffic (time DESC, status)"),
                    # Performance optimized composite indexes
                    ("idx_traffic_host_time", "traffic (host, time DESC)"),
                    ("idx_traffic_ip_time", "traffic (remote_addr, time DESC)"),
                ]

                for idx_name, idx_def in indexes:
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def};")

                # Cleanup problematic objects that cause IMMUTABLE errors
                cur.execute("DROP INDEX IF EXISTS idx_traffic_hourly;")
                cur.execute("DROP MATERIALIZED VIEW IF EXISTS hourly_stats CASCADE;")

                # Create request tracker table for shared blocking state
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS request_tracker (
                        ip_address TEXT PRIMARY KEY,
                        count_404 INTEGER DEFAULT 0,
                        count_403 INTEGER DEFAULT 0,
                        count_5xx INTEGER DEFAULT 0,
                        count_suspicious INTEGER DEFAULT 0,
                        total_failed INTEGER DEFAULT 0,
                        last_update TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                # Create settings table for dynamic configuration
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                logger.info("Database schema initialized successfully")

                # Create blocklist table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS blocklist (
                        id SERIAL PRIMARY KEY,
                        ip_address TEXT NOT NULL UNIQUE,
                        reason TEXT NOT NULL,
                        blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        block_until TIMESTAMPTZ NOT NULL,
                        is_manual BOOLEAN DEFAULT FALSE,
                        unblocked_at TIMESTAMPTZ
                    );
                """)

                # Create whitelist table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS whitelist (
                        ip_address TEXT PRIMARY KEY,
                        reason TEXT,
                        added_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                # Create indexes for blocklist table
                cur.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_ip ON blocklist (ip_address);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_until ON blocklist (block_until);")

                # Create AI analysis table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ai_analysis (
                        id SERIAL PRIMARY KEY,
                        ip_address TEXT NOT NULL,
                        report TEXT NOT NULL,
                        threat_level TEXT,
                        model TEXT,
                        analyzed_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_ip ON ai_analysis (ip_address);")

                return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


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


def insert_traffic_batch(rows: List[Tuple]) -> int:
    """Insert traffic records in batch. Returns number of inserted rows."""
    if not rows:
        return 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                INSERT INTO traffic (time, host, method, path, status, remote_addr,
                                     user_agent, referer, response_length, country_code, city, scheme, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            cur.executemany(query, rows)
            return cur.rowcount


# Request tracker operations for shared blocking state
def update_request_counters(
    ip: str, status: int, is_suspicious: bool = False
) -> Dict[str, int]:
    """Update request counters in DB and return current counts.
    
    Resets counters if last update was more than 5 minutes ago.
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
            # Check if entry exists and is recent
            cur.execute(
                "SELECT * FROM request_tracker WHERE ip_address = %s;", (ip,)
            )
            row = cur.fetchone()
            
            now = datetime.now(timezone.utc)
            reset = False
            if row:
                last_update = row["last_update"]
                if now - last_update > timedelta(minutes=5):
                    reset = True
            
            is_404 = 1 if status == 404 else 0
            is_403 = 1 if status == 403 else 0
            is_5xx = 1 if 500 <= status <= 599 else 0
            is_susp = 1 if is_suspicious else 0
            is_failed = 1 if (is_404 or is_403 or is_5xx or is_susp) else 0

            if not row or reset:
                # Insert or Reset
                cur.execute(
                    """
                    INSERT INTO request_tracker (ip_address, count_404, count_403, count_5xx, count_suspicious, total_failed, last_update)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ip_address) DO UPDATE
                    SET count_404 = EXCLUDED.count_404,
                        count_403 = EXCLUDED.count_403,
                        count_5xx = EXCLUDED.count_5xx,
                        count_suspicious = EXCLUDED.count_suspicious,
                        total_failed = EXCLUDED.total_failed,
                        last_update = EXCLUDED.last_update;
                    """,
                    (ip, is_404, is_403, is_5xx, is_susp, is_failed, now),
                )
            else:
                # Increment
                cur.execute(
                    """
                    UPDATE request_tracker
                    SET count_404 = count_404 + %s,
                        count_403 = count_403 + %s,
                        count_5xx = count_5xx + %s,
                        count_suspicious = count_suspicious + %s,
                        total_failed = total_failed + %s,
                        last_update = %s
                    WHERE ip_address = %s;
                    """,
                    (is_404, is_403, is_5xx, is_susp, is_failed, now, ip),
                )
            
            # Get updated counts
            cur.execute("SELECT * FROM request_tracker WHERE ip_address = %s;", (ip,))
            return cur.fetchone()


def reset_request_counters(ip: str):
    """Reset counters for an IP after blocking."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM request_tracker WHERE ip_address = %s;", (ip,)
            )


def cleanup_old_trackers(max_age_minutes: int = 60):
    """Remove old IPs from tracker to keep table small."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM request_tracker WHERE last_update < %s;", (cutoff,)
            )


def get_tracked_ip_count() -> int:
    """Get the number of IPs currently being tracked for suspicious activity."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM request_tracker;")
            return cur.fetchone()[0]


def cleanup_old_data(days: Optional[int] = None) -> int:
    """Delete data older than specified days. Returns number of deleted rows."""
    retention_days = days if days is not None else app_config.retention_days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    with get_connection() as conn:
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


# Blocklist operations
def add_blocked_ip(
    ip_address: str, reason: str, block_until: datetime, is_manual: bool = False
) -> bool:
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
    hosts: Optional[List[str]] = None,
    recent_minutes: int = 5,
    baseline_minutes: int = 60
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
    params: Dict[str, Any] = {
        "recent_start": recent_start,
        "baseline_start": baseline_start
    }
    
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
                    recent_count >= app_config.spike_min_requests and 
                    current_rate > (baseline_rate * app_config.spike_threshold_factor)
                ) if app_config.enable_anomaly_detection else False
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

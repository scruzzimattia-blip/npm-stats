"""Database operations for NPM Monitor."""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Generator, Any

import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

from .config import db_config, app_config

logger = logging.getLogger(__name__)

# Connection pool (initialized lazily)
_pool: Optional[ThreadedConnectionPool] = None
_engine: Optional[Engine] = None
_db_available: bool = False


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


def get_pool() -> ThreadedConnectionPool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=db_config.pool_min_conn,
            maxconn=db_config.pool_max_conn,
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.name,
            user=db_config.user,
            password=db_config.password,
        )
        logger.info(
            f"Connection pool created (min={db_config.pool_min_conn}, max={db_config.pool_max_conn})"
        )
    return _pool


def get_engine() -> Engine:
    """Get or create SQLAlchemy engine for pandas compatibility."""
    global _engine
    if _engine is None:
        _engine = create_engine(db_config.connection_string)
    return _engine


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for database connections from the pool."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        pool.putconn(conn)


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
                        user_agent TEXT,
                        UNIQUE (time, host, remote_addr, path)
                    );
                """)

                # Add new columns if they don't exist (migration for existing databases)
                new_columns = [
                    ("referer", "TEXT"),
                    ("response_length", "BIGINT"),
                    ("country_code", "CHAR(2)"),
                    ("city", "TEXT"),
                ]

                for col_name, col_type in new_columns:
                    cur.execute(f"""
                        DO $$
                        BEGIN
                            ALTER TABLE traffic ADD COLUMN {col_name} {col_type};
                        EXCEPTION
                            WHEN duplicate_column THEN
                                -- Column already exists, ignore
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
                            -- Column is already BIGINT or doesn't exist, ignore
                            NULL;
                    END $$;
                """)

                # Create indexes for better query performance
                indexes = [
                    ("idx_traffic_time", "traffic (time DESC)"),
                    ("idx_traffic_host", "traffic (host)"),
                    ("idx_traffic_remote_addr", "traffic (remote_addr)"),
                    ("idx_traffic_status", "traffic (status)"),
                    ("idx_traffic_time_host", "traffic (time DESC, host)"),
                    ("idx_traffic_country", "traffic (country_code)"),
                ]

                for idx_name, idx_def in indexes:
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def};
                    """)

                logger.info("Database schema initialized successfully")
                return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def insert_traffic_batch(rows: List[Tuple]) -> int:
    """Insert traffic records in batch. Returns number of inserted rows."""
    if not rows:
        return 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                INSERT INTO traffic (time, host, method, path, status, remote_addr,
                                     user_agent, referer, response_length, country_code, city)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, host, remote_addr, path) DO NOTHING;
            """
            execute_batch(cur, query, rows, page_size=1000)
            return cur.rowcount


def cleanup_old_data(days: Optional[int] = None) -> int:
    """Delete data older than specified days. Returns number of deleted rows."""
    retention_days = days if days is not None else app_config.retention_days
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM traffic WHERE time < %s",
                (cutoff_date,)
            )
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


def get_distinct_hosts() -> List[str]:
    """Get list of distinct hosts."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT host FROM traffic ORDER BY host;")
            return [row[0] for row in cur.fetchall()]


def get_traffic_stats(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """Get aggregated traffic statistics."""
    conditions = []
    params: List[Any] = []

    if hosts:
        conditions.append("host = ANY(%s)")
        params.append(hosts)
    if start_date:
        conditions.append("time >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("time <= %s")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_requests,
                    COUNT(DISTINCT remote_addr) as unique_ips,
                    COUNT(DISTINCT host) as distinct_hosts,
                    COUNT(CASE WHEN status >= 400 THEN 1 END) as error_count,
                    COUNT(DISTINCT country_code) as distinct_countries,
                    MIN(time) as first_request,
                    MAX(time) as last_request
                FROM traffic
                {where_clause};
            """, params or None)
            return dict(cur.fetchone())


def get_database_info() -> dict:
    """Get database statistics."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    pg_size_pretty(pg_total_relation_size('traffic')) as table_size,
                    MIN(time) as oldest_record,
                    MAX(time) as newest_record
                FROM traffic;
            """)
            return dict(cur.fetchone())


def health_check() -> bool:
    """Check database connectivity."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


def load_traffic_df(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50000,
) -> pd.DataFrame:
    """Load traffic data from database as DataFrame using SQLAlchemy."""
    conditions = []
    params: dict = {}

    if hosts:
        # Use IN clause with tuple for SQLAlchemy
        placeholders = ", ".join([f":host_{i}" for i in range(len(hosts))])
        conditions.append(f"host IN ({placeholders})")
        for i, host in enumerate(hosts):
            params[f"host_{i}"] = host
    if start_date:
        conditions.append("time >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("time <= :end_date")
        params["end_date"] = end_date

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params["limit"] = limit

    query = f"""
        SELECT time, host, method, path, status, remote_addr,
               user_agent, referer, response_length, country_code, city
        FROM traffic
        {where_clause}
        ORDER BY time DESC
        LIMIT :limit;
    """

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])

    return df

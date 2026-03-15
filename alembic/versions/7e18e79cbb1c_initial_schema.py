"""initial_schema

Revision ID: 7e18e79cbb1c
Revises:
Create Date: 2026-03-14 23:51:31.992549

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e18e79cbb1c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS traffic (
            id SERIAL PRIMARY KEY,
            time TIMESTAMPTZ NOT NULL,
            host TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status INTEGER NOT NULL,
            remote_addr TEXT NOT NULL,
            user_agent TEXT,
            referer TEXT,
            response_length BIGINT,
            country_code CHAR(2),
            city TEXT,
            scheme TEXT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_time ON traffic (time DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_host ON traffic (host);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_remote_addr ON traffic (remote_addr);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_status ON traffic (status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_time_host ON traffic (time DESC, host);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_country ON traffic (country_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_host_status ON traffic (host, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_time_status ON traffic (time DESC, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_host_time ON traffic (host, time DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_ip_time ON traffic (remote_addr, time DESC);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS request_tracker (
            ip_address TEXT PRIMARY KEY,
            count_404 INTEGER DEFAULT 0,
            count_403 INTEGER DEFAULT 0,
            count_5xx INTEGER DEFAULT 0,
            count_suspicious INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            last_update TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_ip ON blocklist (ip_address);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_until ON blocklist (block_until);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            ip_address TEXT PRIMARY KEY,
            reason TEXT,
            added_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis (
            id SERIAL PRIMARY KEY,
            ip_address TEXT NOT NULL,
            report TEXT NOT NULL,
            threat_level TEXT,
            model TEXT,
            analyzed_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_ip ON ai_analysis (ip_address);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS asn_blocklist (
            id SERIAL PRIMARY KEY,
            asn TEXT NOT NULL UNIQUE,
            description TEXT,
            blocked_at TIMESTAMPTZ DEFAULT NOW(),
            reason TEXT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS host_health (
            host TEXT PRIMARY KEY,
            is_up BOOLEAN DEFAULT TRUE,
            last_check TIMESTAMPTZ DEFAULT NOW(),
            status_code INTEGER,
            ssl_expiry TIMESTAMPTZ,
            response_time FLOAT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS host_health;")
    op.execute("DROP TABLE IF EXISTS asn_blocklist;")
    op.execute("DROP TABLE IF EXISTS ai_analysis;")
    op.execute("DROP TABLE IF EXISTS whitelist;")
    op.execute("DROP TABLE IF EXISTS blocklist;")
    op.execute("DROP TABLE IF EXISTS app_settings;")
    op.execute("DROP TABLE IF EXISTS request_tracker;")
    op.execute("DROP TABLE IF EXISTS traffic;")

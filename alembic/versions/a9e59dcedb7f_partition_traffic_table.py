"""partition_traffic_table

Revision ID: a9e59dcedb7f
Revises: 7e18e79cbb1c
Create Date: 2026-03-14 23:53:48.601376

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a9e59dcedb7f'
down_revision: Union[str, Sequence[str], None] = '7e18e79cbb1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE traffic RENAME TO traffic_old;")
    op.execute("ALTER TABLE traffic_old DROP CONSTRAINT IF EXISTS traffic_pkey;")

    op.execute("""
        CREATE TABLE traffic (
            id SERIAL,
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
            longitude DOUBLE PRECISION,
            PRIMARY KEY (id, time)
        ) PARTITION BY RANGE (time);
    """)

    op.execute("CREATE TABLE traffic_default PARTITION OF traffic DEFAULT;")
    op.execute("INSERT INTO traffic SELECT * FROM traffic_old;")
    op.execute("DROP TABLE traffic_old CASCADE;")

    # Recreate indexes on the master table (will cascade to partitions)
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_time_p ON traffic (time DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_host_p ON traffic (host);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_remote_addr_p ON traffic (remote_addr);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_status_p ON traffic (status);")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE traffic RENAME TO traffic_partitioned;")
    op.execute("ALTER TABLE traffic_partitioned DROP CONSTRAINT IF EXISTS traffic_pkey;")

    op.execute("""
        CREATE TABLE traffic (
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
    op.execute("INSERT INTO traffic (id, time, host, method, path, status, remote_addr, user_agent, referer, response_length, country_code, city, scheme, latitude, longitude) SELECT id, time, host, method, path, status, remote_addr, user_agent, referer, response_length, country_code, city, scheme, latitude, longitude FROM traffic_partitioned;")
    op.execute("DROP TABLE traffic_partitioned CASCADE;")

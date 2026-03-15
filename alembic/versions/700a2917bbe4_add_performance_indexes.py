"""add_performance_indexes

Revision ID: 700a2917bbe4
Revises: 600a2917bbe4
Create Date: 2026-03-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '700a2917bbe4'
down_revision: Union[str, Sequence[str], None] = '600a2917bbe4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema - add performance indexes."""
    # Composite index for filtering by host and time (most common Dashboard query)
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_host_time ON traffic (host, time DESC)")

    # Index for status codes (important for error analysis)
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_status ON traffic (status)")

    # Index for remote_addr (important for IP analysis and blocking)
    op.execute("CREATE INDEX IF NOT EXISTS idx_traffic_remote_addr ON traffic (remote_addr)")

def downgrade() -> None:
    """Downgrade schema - remove performance indexes."""
    op.execute("DROP INDEX IF EXISTS idx_traffic_host_time")
    op.execute("DROP INDEX IF EXISTS idx_traffic_status")
    op.execute("DROP INDEX IF EXISTS idx_traffic_remote_addr")

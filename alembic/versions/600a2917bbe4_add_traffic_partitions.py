"""add_traffic_partitions

Revision ID: 600a2917bbe4
Revises: 529a2917bbe4
Create Date: 2026-03-15 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '600a2917bbe4'
down_revision: Union[str, Sequence[str], None] = '529a2917bbe4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema - create monthly partitions for traffic table."""
    # 1. Check if traffic_default has data and move it to a temp table
    op.execute("CREATE TABLE IF NOT EXISTS traffic_temp (LIKE traffic INCLUDING ALL)")
    op.execute("INSERT INTO traffic_temp SELECT * FROM traffic_default")
    op.execute("TRUNCATE traffic_default")

    # 2. Create partitions for 2026
    for month in range(3, 13):
        start_date = f'2026-{month:02d}-01'
        if month == 12:
            end_date = '2027-01-01'
        else:
            end_date = f'2026-{month+1:02d}-01'
        
        partition_name = f'traffic_y2026m{month:02d}'
        op.execute(f"CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF traffic FOR VALUES FROM ('{start_date}') TO ('{end_date}')")

    # 3. Restore data from temp table (it will automatically go into the correct partitions)
    op.execute("INSERT INTO traffic SELECT * FROM traffic_temp")
    op.execute("DROP TABLE traffic_temp")

def downgrade() -> None:
    """Downgrade schema - detach partitions (careful, data loss if not moved back to default)."""
    for month in range(3, 13):
        partition_name = f'traffic_y2026m{month:02d}'
        op.execute(f"DROP TABLE IF EXISTS {partition_name}")

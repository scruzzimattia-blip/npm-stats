"""add_totp_secret

Revision ID: 529a2917bbe4
Revises: a9e59dcedb7f
Create Date: 2026-03-14 23:54:23.884318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '529a2917bbe4'
down_revision: Union[str, Sequence[str], None] = 'a9e59dcedb7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT;")

def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS totp_secret;")

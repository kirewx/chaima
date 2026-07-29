"""add chemical sds_url

Revision ID: c8a1f2d3e4b5
Revises: b7e9d1f3a5c7
Create Date: 2026-07-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a1f2d3e4b5'
down_revision: Union[str, Sequence[str], None] = 'b7e9d1f3a5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chemical',
        sa.Column('sds_url', sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chemical', 'sds_url')

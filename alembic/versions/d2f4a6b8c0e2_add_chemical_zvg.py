"""add chemical zvg

Revision ID: d2f4a6b8c0e2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd2f4a6b8c0e2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chemical',
        sa.Column('zvg', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chemical', 'zvg')

"""add group show_sds_research_links

Revision ID: b7e9d1f3a5c7
Revises: d2f4a6b8c0e2
Create Date: 2026-07-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e9d1f3a5c7'
down_revision: Union[str, Sequence[str], None] = 'd2f4a6b8c0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'group',
        sa.Column(
            'show_sds_research_links',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('1'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('group', 'show_sds_research_links')

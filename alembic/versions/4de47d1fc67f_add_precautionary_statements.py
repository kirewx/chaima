"""add precautionary statements

Revision ID: 4de47d1fc67f
Revises: f608356fe048
Create Date: 2026-06-30 23:22:43.339448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4de47d1fc67f'
down_revision: Union[str, Sequence[str], None] = 'f608356fe048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "p_statement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_p_statement_code"), "p_statement", ["code"], unique=True)

    op.create_table(
        "chemical_p_statement",
        sa.Column("chemical_id", sa.Uuid(), nullable=False),
        sa.Column("p_statement_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["chemical_id"], ["chemical.id"]),
        sa.ForeignKeyConstraint(["p_statement_id"], ["p_statement.id"]),
        sa.PrimaryKeyConstraint("chemical_id", "p_statement_id"),
        sa.UniqueConstraint("chemical_id", "p_statement_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("chemical_p_statement")
    op.drop_index(op.f("ix_p_statement_code"), table_name="p_statement")
    op.drop_table("p_statement")

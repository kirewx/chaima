"""drop chemical.image_path and chemical.structure_source

Revision ID: b4e7c1a29301
Revises: 49c7178e33a9
Create Date: 2026-04-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "b4e7c1a29301"
down_revision: Union[str, Sequence[str], None] = "49c7178e33a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chemical") as batch_op:
        batch_op.drop_column("image_path")
        batch_op.drop_column("structure_source")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="structuresource").drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    structuresource = sa.Enum("NONE", "PUBCHEM", "UPLOADED", name="structuresource")
    if bind.dialect.name == "postgresql":
        structuresource.create(bind, checkfirst=True)

    with op.batch_alter_table("chemical") as batch_op:
        batch_op.add_column(
            sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "structure_source",
                structuresource,
                nullable=False,
                server_default="NONE",
            )
        )

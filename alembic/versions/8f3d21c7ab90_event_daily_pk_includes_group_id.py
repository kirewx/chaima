"""event_daily: PK includes group_id, user_id nullable

The compaction job aggregates by (day, user_id, type, group_id), so the
primary key must match — otherwise same-day activity in two groups collides
into one row. user_id becomes nullable so anonymous events (login_failure)
survive compaction instead of being silently dropped.

SQLite cannot alter primary keys in place; batch_alter_table recreates the
table and copies the rows. The old key (day, user_id, type) is strictly
narrower than the new one, so existing rows cannot conflict on upgrade.

Revision ID: 8f3d21c7ab90
Revises: 4de47d1fc67f
Create Date: 2026-07-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '8f3d21c7ab90'
down_revision: Union[str, Sequence[str], None] = '4de47d1fc67f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _copy_from(user_id_nullable: bool) -> sa.Table:
    """Describe event_daily WITHOUT a primary key so the batch recreate can
    install the desired one via create_primary_key."""
    meta = sa.MetaData()
    return sa.Table(
        "event_daily", meta,
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=user_id_nullable),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("event_daily", copy_from=_copy_from(user_id_nullable=True)) as batch_op:
        batch_op.create_primary_key(
            "pk_event_daily", ["day", "user_id", "type", "group_id"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    # The narrower key (day, user_id, type) cannot represent anonymous rows
    # or per-group splits: drop NULL-user rows, then merge duplicates by
    # summing their counts into one survivor per (day, user_id, type).
    op.execute("DELETE FROM event_daily WHERE user_id IS NULL")
    op.execute(
        """
        UPDATE event_daily
        SET count = (
            SELECT SUM(ed2.count) FROM event_daily AS ed2
            WHERE ed2.day = event_daily.day
              AND ed2.user_id = event_daily.user_id
              AND ed2.type = event_daily.type
        )
        WHERE rowid IN (
            SELECT MIN(rowid) FROM event_daily GROUP BY day, user_id, type
        )
        """
    )
    op.execute(
        """
        DELETE FROM event_daily
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM event_daily GROUP BY day, user_id, type
        )
        """
    )
    with op.batch_alter_table("event_daily", copy_from=_copy_from(user_id_nullable=False)) as batch_op:
        batch_op.create_primary_key(
            "pk_event_daily", ["day", "user_id", "type"]
        )

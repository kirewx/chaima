"""add analytics tables and user login counters

Revision ID: f608356fe048
Revises: 45d05a16c2d1
Create Date: 2026-05-27 14:38:16.239644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f608356fe048'
down_revision: Union[str, Sequence[str], None] = '45d05a16c2d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- analytics tables ---
    op.create_table(
        "event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_user_id"), "event", ["user_id"], unique=False)
    op.create_index(op.f("ix_event_group_id"), "event", ["group_id"], unique=False)
    op.create_index(op.f("ix_event_type"), "event", ["type"], unique=False)
    op.create_index(op.f("ix_event_created_at"), "event", ["created_at"], unique=False)
    op.create_index("ix_event_user_created", "event", ["user_id", "created_at"], unique=False)
    op.create_index("ix_event_type_created", "event", ["type", "created_at"], unique=False)

    op.create_table(
        "event_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("day", "user_id", "type"),
    )

    op.create_table(
        "slow_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_slow_request_path"), "slow_request", ["path"], unique=False)
    op.create_index(op.f("ix_slow_request_created_at"), "slow_request", ["created_at"], unique=False)
    op.create_index("ix_slow_path_created", "slow_request", ["path", "created_at"], unique=False)

    # --- user counters ---
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("login_count", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("login_count")
        batch_op.drop_column("last_login_at")

    op.drop_index("ix_slow_path_created", table_name="slow_request")
    op.drop_index(op.f("ix_slow_request_created_at"), table_name="slow_request")
    op.drop_index(op.f("ix_slow_request_path"), table_name="slow_request")
    op.drop_table("slow_request")

    op.drop_table("event_daily")

    op.drop_index("ix_event_type_created", table_name="event")
    op.drop_index("ix_event_user_created", table_name="event")
    op.drop_index(op.f("ix_event_created_at"), table_name="event")
    op.drop_index(op.f("ix_event_type"), table_name="event")
    op.drop_index(op.f("ix_event_group_id"), table_name="event")
    op.drop_index(op.f("ix_event_user_id"), table_name="event")
    op.drop_table("event")

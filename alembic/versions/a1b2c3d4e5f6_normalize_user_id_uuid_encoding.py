"""normalize user.id UUID encoding to undashed 32-hex

fastapi-users' default ``GUID`` type stored ``user.id`` as a *dashed*
CHAR(36) string (e.g. ``8a9f8a43-1547-4203-8738-1878cc19544d``). Every
column that references ``user.id`` (``created_by``, ``user_id``, ...) is a
SQLModel ``uuid.UUID`` mapped to SQLAlchemy ``Uuid`` and is stored *undashed*
(``8a9f8a431547420387381878cc19544d``). The two encodings never matched, so
with ``PRAGMA foreign_keys=ON`` every FK to a user dangled and inserts that
referenced a user (containers, chemicals, invites, orders, ...) failed.

The model now pins ``user.id`` to ``Uuid`` (undashed). This migration brings
existing rows into line by stripping the dashes from ``user.id``. All
referencing columns are already undashed, so no child rows need touching:
once the parent key is de-dashed, the previously dangling FKs line up.

Safe under FK enforcement: no child column references the *dashed* value, so
de-dashing the parent PK does not orphan anything — it repairs the match.
Idempotent: REPLACE on an already-undashed id is a no-op.

Revision ID: a1b2c3d4e5f6
Revises: 8f3d21c7ab90
Create Date: 2026-07-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8f3d21c7ab90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only the SQLite deployments carry the dashed encoding; on PostgreSQL the
    # native UUID type is used on both sides and there is nothing to normalize.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    op.execute(
        """
        UPDATE "user"
        SET id = REPLACE(id, '-', '')
        WHERE id LIKE '%-%'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    # Reconstruct the dashed 8-4-4-4-12 form from the 32-hex string.
    op.execute(
        """
        UPDATE "user"
        SET id =
            substr(id, 1, 8)  || '-' ||
            substr(id, 9, 4)  || '-' ||
            substr(id, 13, 4) || '-' ||
            substr(id, 17, 4) || '-' ||
            substr(id, 21, 12)
        WHERE id NOT LIKE '%-%' AND length(id) = 32
        """
    )

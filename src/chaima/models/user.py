import datetime
import uuid as uuid_pkg

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chaima.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    # Override the fastapi-users id column type. Its default ``GUID`` stores
    # UUIDs as a *dashed* CHAR(36) string, whereas every column that references
    # ``user.id`` (created_by, user_id, ...) is a SQLModel ``uuid.UUID`` mapped
    # to SQLAlchemy ``Uuid`` — stored *undashed* (32-hex) on SQLite. The two
    # encodings never match, so with ``PRAGMA foreign_keys=ON`` every FK to a
    # user dangled. Using ``Uuid`` here makes user.id share the app's encoding.
    # Migration ``a1b2c3d4e5f6`` normalizes the existing dashed rows.
    id: Mapped[uuid_pkg.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_pkg.uuid4
    )

    main_group_id: Mapped[uuid_pkg.UUID | None] = mapped_column(
        ForeignKey("group.id"), nullable=True, default=None
    )
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="0", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Analytics: cheap counters bumped from UserManager.on_after_login.
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    created_chemicals: Mapped[list["Chemical"]] = relationship(
        "Chemical", back_populates="creator", foreign_keys="[Chemical.created_by]"
    )
    created_containers: Mapped[list["Container"]] = relationship(
        "Container", back_populates="creator", foreign_keys="[Container.created_by]"
    )

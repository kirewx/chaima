import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chaima.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    created_chemicals: Mapped[list["Chemical"]] = relationship(
        "Chemical", back_populates="creator", foreign_keys="[Chemical.created_by]"
    )
    created_containers: Mapped[list["Container"]] = relationship(
        "Container", back_populates="creator", foreign_keys="[Container.created_by]"
    )

import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, Relationship, SQLModel


class ImportLog(SQLModel, table=True):
    __tablename__ = "import_log"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    file_name: str
    imported_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    row_count: int
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    group: "Group" = Relationship()
    user: "User" = Relationship()

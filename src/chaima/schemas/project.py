import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None


class ProjectRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    name: str
    is_archived: bool
    created_at: datetime.datetime

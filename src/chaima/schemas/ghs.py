# src/chaima/schemas/ghs.py
from uuid import UUID

from pydantic import BaseModel


class GHSCodeCreate(BaseModel):
    code: str
    description: str
    pictogram: str | None = None
    signal_word: str | None = None


class GHSCodeUpdate(BaseModel):
    description: str | None = None
    pictogram: str | None = None
    signal_word: str | None = None


class GHSCodeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    code: str
    description: str
    pictogram: str | None
    signal_word: str | None

# src/chaima/schemas/hazard.py
from uuid import UUID

from pydantic import BaseModel


class HazardTagCreate(BaseModel):
    """Schema for creating a hazard tag.

    Attributes
    ----------
    name : str
        Name of the hazard tag.
    description : str or None
        Optional description.
    """

    name: str
    description: str | None = None


class HazardTagUpdate(BaseModel):
    """Schema for updating a hazard tag.

    Attributes
    ----------
    name : str or None
        New name, if provided.
    description : str or None
        New description, if provided.
    """

    name: str | None = None
    description: str | None = None


class HazardTagRead(BaseModel):
    """Schema for reading a hazard tag.

    Attributes
    ----------
    id : UUID
        Unique identifier.
    name : str
        Name of the hazard tag.
    description : str or None
        Optional description.
    group_id : UUID
        The group this tag belongs to.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    group_id: UUID


class IncompatibilityCreate(BaseModel):
    """Schema for creating a hazard tag incompatibility rule.

    Attributes
    ----------
    tag_a_id : UUID
        ID of the first hazard tag.
    tag_b_id : UUID
        ID of the second hazard tag.
    reason : str or None
        Optional reason for the incompatibility.
    """

    tag_a_id: UUID
    tag_b_id: UUID
    reason: str | None = None


class IncompatibilityRead(BaseModel):
    """Schema for reading a hazard tag incompatibility rule.

    Attributes
    ----------
    id : UUID
        Unique identifier.
    tag_a_id : UUID
        ID of the first hazard tag (canonical lower UUID).
    tag_b_id : UUID
        ID of the second hazard tag (canonical higher UUID).
    reason : str or None
        Optional reason for the incompatibility.
    """

    model_config = {"from_attributes": True}

    id: UUID
    tag_a_id: UUID
    tag_b_id: UUID
    reason: str | None

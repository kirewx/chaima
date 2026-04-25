from __future__ import annotations

import datetime
from uuid import UUID

from pydantic import BaseModel

from chaima.models.storage import StorageKind


class StorageLocationCreate(BaseModel):
    """Schema for creating a storage location.

    Attributes
    ----------
    name : str
        Human-readable name for the location.
    kind : StorageKind
        The kind of storage location (building, room, cabinet, shelf).
    description : str or None
        Optional description.
    parent_id : UUID or None
        Optional parent location ID for nesting.
    """

    name: str
    kind: StorageKind
    description: str | None = None
    parent_id: UUID | None = None
    color: str | None = None


class StorageLocationUpdate(BaseModel):
    """Schema for updating a storage location.

    Attributes
    ----------
    name : str or None
        New name, if provided.
    description : str or None
        New description, if provided.
    parent_id : UUID or None
        New parent location ID, if provided.
    """

    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    color: str | None = None


class StorageLocationRead(BaseModel):
    """Schema for reading a storage location.

    Attributes
    ----------
    id : UUID
        Unique identifier.
    name : str
        Human-readable name.
    kind : StorageKind
        The kind of storage location.
    description : str or None
        Optional description.
    parent_id : UUID or None
        Parent location ID, if any.
    created_at : datetime.datetime
        Creation timestamp.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    kind: StorageKind
    description: str | None
    parent_id: UUID | None
    color: str | None
    created_at: datetime.datetime


class StorageLocationNode(BaseModel):
    """Recursive node for the storage location tree.

    Attributes
    ----------
    id : UUID
        Unique identifier.
    name : str
        Human-readable name.
    kind : StorageKind
        The kind of storage location.
    description : str or None
        Optional description.
    parent_id : UUID or None
        Parent location ID, if any.
    container_count : int
        Number of non-archived containers pinned directly to this node
        (not transitive — does not include containers in descendant nodes).
    children : list[StorageLocationNode]
        Child nodes in the tree.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    kind: StorageKind
    description: str | None
    parent_id: UUID | None
    color: str | None = None
    container_count: int = 0
    children: list[StorageLocationNode] = []

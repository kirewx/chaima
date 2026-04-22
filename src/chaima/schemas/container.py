# src/chaima/schemas/container.py
import datetime
from uuid import UUID

from pydantic import BaseModel


class ContainerCreate(BaseModel):
    """Schema for creating a container.

    Parameters
    ----------
    location_id : UUID
        The storage location for this container.
    supplier_id : UUID or None, optional
        The supplier this container came from.
    identifier : str
        A human-readable identifier (e.g. bottle number or lot ID).
    amount : float
        Quantity of chemical in this container.
    unit : str
        Unit of measurement (e.g. mL, g).
    purchased_at : datetime.date or None, optional
        Purchase date.
    ordered_by_name : str or None, optional
        Name of the person who ordered this container.
    """

    location_id: UUID
    supplier_id: UUID | None = None
    identifier: str
    amount: float
    unit: str
    purchased_at: datetime.date | None = None
    ordered_by_name: str | None = None


class ContainerUpdate(BaseModel):
    """Schema for partial update of a container.

    All fields are optional. Use ``is_archived: false`` to unarchive.

    Parameters
    ----------
    location_id : UUID or None, optional
        New storage location.
    supplier_id : UUID or None, optional
        New supplier.
    identifier : str or None, optional
        New identifier.
    amount : float or None, optional
        New amount.
    unit : str or None, optional
        New unit.
    purchased_at : datetime.date or None, optional
        New purchase date.
    ordered_by_name : str or None, optional
        New name of the person who ordered this container.
    is_archived : bool or None, optional
        Set to False to unarchive, True to archive.
    """

    location_id: UUID | None = None
    supplier_id: UUID | None = None
    identifier: str | None = None
    amount: float | None = None
    unit: str | None = None
    purchased_at: datetime.date | None = None
    ordered_by_name: str | None = None
    is_archived: bool | None = None


class ContainerRead(BaseModel):
    """Schema for reading a container.

    Parameters
    ----------
    id : UUID
        Container ID.
    chemical_id : UUID
        Parent chemical ID.
    location_id : UUID
        Storage location ID.
    supplier_id : UUID or None
        Supplier ID (if any).
    identifier : str
        Human-readable identifier.
    amount : float
        Quantity of chemical.
    unit : str
        Unit of measurement.
    image_path : str or None
        Path to container image.
    purchased_at : datetime.date or None
        Purchase date.
    ordered_by_name : str or None
        Name of the person who ordered this container.
    created_by : UUID
        ID of the user who created this container.
    created_at : datetime.datetime
        Creation timestamp.
    updated_at : datetime.datetime
        Last update timestamp.
    is_archived : bool
        Whether this container has been soft-deleted.
    """

    model_config = {"from_attributes": True}

    id: UUID
    chemical_id: UUID
    location_id: UUID
    supplier_id: UUID | None
    identifier: str
    amount: float
    unit: str
    image_path: str | None
    purchased_at: datetime.date | None
    ordered_by_name: str | None
    created_by: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_archived: bool

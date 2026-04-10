import datetime
from uuid import UUID

from pydantic import BaseModel


class GroupCreate(BaseModel):
    """Schema for creating a group.

    Attributes
    ----------
    name : str
        The name of the group.
    description : str or None
        Optional description of the group.
    """

    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    """Schema for updating a group.

    Attributes
    ----------
    name : str or None
        New name for the group, if provided.
    description : str or None
        New description for the group, if provided.
    """

    name: str | None = None
    description: str | None = None


class GroupRead(BaseModel):
    """Schema for reading a group.

    Attributes
    ----------
    id : UUID
        The unique identifier of the group.
    name : str
        The name of the group.
    description : str or None
        Optional description of the group.
    created_at : datetime.datetime
        When the group was created.
    """

    id: UUID
    name: str
    description: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    """Schema for adding a member to a group.

    Attributes
    ----------
    user_id : UUID
        The ID of the user to add.
    is_admin : bool
        Whether the user should be an admin. Defaults to False.
    """

    user_id: UUID
    is_admin: bool = False


class MemberUpdate(BaseModel):
    """Schema for updating a member's role in a group.

    Attributes
    ----------
    is_admin : bool
        Whether the user should be an admin.
    """

    is_admin: bool


class MemberRead(BaseModel):
    """Schema for reading a group membership.

    Attributes
    ----------
    user_id : UUID
        The ID of the member user.
    group_id : UUID
        The ID of the group.
    is_admin : bool
        Whether the user is an admin of the group.
    joined_at : datetime.datetime
        When the user joined the group.
    email : str
        The email address of the member user.
    """

    user_id: UUID
    group_id: UUID
    is_admin: bool
    joined_at: datetime.datetime
    email: str

    model_config = {"from_attributes": True}

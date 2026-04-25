import datetime
from uuid import UUID

from pydantic import BaseModel


class InviteCreate(BaseModel):
    """Schema for creating an invite — no body fields needed, group_id from path."""

    pass


class InviteRead(BaseModel):
    """Full invite details for admin views.

    Attributes
    ----------
    id : UUID
        The invite ID.
    group_id : UUID
        The group this invite is for.
    token : str
        The invite token.
    created_by : UUID
        The user who created the invite.
    expires_at : datetime.datetime
        When the invite expires.
    used_by : UUID or None
        The user who accepted the invite, if any.
    used_at : datetime.datetime or None
        When the invite was accepted.
    """

    id: UUID
    group_id: UUID
    token: str
    created_by: UUID
    expires_at: datetime.datetime
    used_by: UUID | None
    used_at: datetime.datetime | None
    invite_url: str | None = None

    model_config = {"from_attributes": True}


class InviteInfo(BaseModel):
    """Public invite info for the landing page.

    Attributes
    ----------
    group_name : str
        Name of the group being invited to.
    expires_at : datetime.datetime
        When the invite expires.
    is_valid : bool
        Whether the invite can still be used.
    """

    group_name: str
    expires_at: datetime.datetime
    is_valid: bool


class InviteAccept(BaseModel):
    """Schema for accepting an invite as a new user.

    Attributes
    ----------
    email : str
        Email for the new account.
    password : str
        Password for the new account.
    """

    email: str
    password: str

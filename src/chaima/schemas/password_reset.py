import datetime

from pydantic import BaseModel, Field


class ResetLinkRead(BaseModel):
    """An admin-issued password reset link.

    Attributes
    ----------
    token : str
        The reset token.
    reset_url : str or None
        Full URL to hand to the user. ``None`` when ``public_base_url`` is
        unset, in which case the frontend falls back to its own origin.
    expires_at : datetime.datetime
        When the token stops working. Returned for display only; the JWT
        carries its own ``exp`` claim, which is what is actually enforced.
    """

    token: str
    reset_url: str | None = None
    expires_at: datetime.datetime


class PasswordResetPerform(BaseModel):
    """Body for redeeming a reset token.

    Attributes
    ----------
    token : str
        The token from the reset link.
    password : str
        The new password (minimum 8 characters).
    """

    token: str
    password: str = Field(min_length=8)

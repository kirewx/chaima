"""Public endpoint for redeeming a password reset token.

Deliberately separate from the authenticated user routes: everything here
is reachable without a session, and mounting it beside routes that assume
one invites mistakes.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi_users import exceptions

from chaima.auth import UserManager, get_user_manager
from chaima.models.analytics import EventType
from chaima.schemas.password_reset import PasswordResetDone, PasswordResetPerform
from chaima.services.events import log_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/reset-password", response_model=PasswordResetDone)
async def reset_password(
    body: PasswordResetPerform,
    background_tasks: BackgroundTasks,
    user_manager: UserManager = Depends(get_user_manager),
) -> PasswordResetDone:
    """Set a new password using an admin-issued reset token.

    There is deliberately no companion endpoint for inspecting a token
    before redemption — it would let anyone probe whether a token is live.

    Parameters
    ----------
    body : PasswordResetPerform
        The token and the new password.
    background_tasks : BackgroundTasks
        Runner for the audit write (injected).
    user_manager : UserManager
        Verifies the token and writes the new password (injected).

    Returns
    -------
    PasswordResetDone
        A detail message.

    Raises
    ------
    HTTPException
        400 if the token is invalid, expired or already used, or if the
        password fails validation.
    """
    try:
        user = await user_manager.reset_password(body.token, body.password)
    except (
        exceptions.InvalidResetPasswordToken,
        exceptions.UserNotExists,
        exceptions.UserInactive,
    ):
        # One message for all three: distinguishing them would tell an
        # unauthenticated caller whether an account exists.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link is invalid or has expired",
        )
    except exceptions.InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc.reason),
        )

    log_event(
        background_tasks,
        user_id=user.id,
        group_id=None,
        type=EventType.PASSWORD_RESET_COMPLETED,
        payload=None,
    )

    return PasswordResetDone(detail="Password updated")

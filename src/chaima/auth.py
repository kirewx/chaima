import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.jwt import generate_jwt
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.config import admin_settings, settings
from chaima.db import get_async_session
from chaima.models.user import User


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key.get_secret_value()
    verification_token_secret = settings.secret_key.get_secret_value()
    reset_password_token_lifetime_seconds = (
        admin_settings.password_reset_ttl_hours * 3600
    )

    def generate_reset_token(self, user: User) -> str:
        """Build a password-reset token without delivering it anywhere.

        ``forgot_password()`` passes its token to ``on_after_forgot_password``
        and returns None, which is the wrong shape when an admin needs the
        value to hand over out of band. The claims below must stay identical
        to the ones that method builds, or ``reset_password()`` will reject
        what we issue.

        The ``password_fgpt`` claim is a hash of the user's current password
        hash; ``reset_password()`` re-verifies it against the stored value,
        so any password change invalidates every outstanding token.

        Parameters
        ----------
        user : User
            The user whose password is to be reset.

        Returns
        -------
        str
            A signed JWT accepted by ``reset_password()``.
        """
        token_data = {
            "sub": str(user.id),
            "password_fgpt": self.password_helper.hash(user.hashed_password),
            "aud": self.reset_password_token_audience,
        }
        return generate_jwt(
            token_data,
            self.reset_password_token_secret,
            self.reset_password_token_lifetime_seconds,
        )

    async def on_after_login(self, user, request=None, response=None):
        """Bump login counters and emit a login_success event.

        Login is a low-frequency, intrinsically slow path (password hashing),
        so writing inline is fine — no BackgroundTasks needed.
        """
        import datetime as _dt

        from chaima.services.events import _persist_event

        now = _dt.datetime.now(_dt.timezone.utc)
        try:
            await self.user_db.update(
                user, {"last_login_at": now, "login_count": (user.login_count or 0) + 1}
            )
        except Exception:  # noqa: BLE001
            pass  # never fail the login over telemetry

        await _persist_event(
            user_id=user.id,
            group_id=getattr(user, "main_group_id", None),
            type="login_success",
            payload=None,
        )

    async def authenticate(self, credentials):
        """Wrap fastapi-users' authenticate to log failed-login attempts."""
        from chaima.services.events import _persist_event

        result = await super().authenticate(credentials)
        if result is None:
            email = getattr(credentials, "username", None)
            await _persist_event(
                user_id=None,
                group_id=None,
                type="login_failure",
                payload={"email_attempted": email},
            )
        return result


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


_SESSION_LIFETIME_SECONDS = settings.session_ttl_hours * 3600

cookie_transport = CookieTransport(
    cookie_max_age=_SESSION_LIFETIME_SECONDS,
    cookie_secure=settings.cookie_secure,
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key.get_secret_value(),
        lifetime_seconds=_SESSION_LIFETIME_SECONDS,
    )


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager=get_user_manager,
    auth_backends=[auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
optional_current_user = fastapi_users.current_user(active=True, optional=True)

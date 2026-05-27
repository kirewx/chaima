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
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.config import settings
from chaima.db import get_async_session
from chaima.models.user import User


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key.get_secret_value()
    verification_token_secret = settings.secret_key.get_secret_value()

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


cookie_transport = CookieTransport(
    cookie_max_age=3600,
    cookie_secure=settings.cookie_secure,
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key.get_secret_value(), lifetime_seconds=3600
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

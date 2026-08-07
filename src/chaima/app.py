import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.staticfiles import StaticFiles

from chaima.auth import auth_backend, fastapi_users
from chaima.config import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_SECRET_KEY,
    admin_settings,
    settings,
)
from chaima.db import async_session_maker, create_db_and_tables
from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User
from chaima.routers.chemicals import router as chemicals_router
from chaima.routers.compatibility import router as compatibility_router
from chaima.routers.pubchem import router as pubchem_router
from chaima.routers.containers import router as containers_router
from chaima.routers.ghs import router as ghs_router
from chaima.routers.groups import router as groups_router
from chaima.routers.password_reset import router as password_reset_router
from chaima.routers.users import router as users_custom_router
from chaima.routers.hazard_tags import router as hazard_tags_router
from chaima.routers.invites import router as invites_router
from chaima.routers.storage_locations import router as storage_locations_router
from chaima.routers.import_ import router as import_router
from chaima.routers.projects import router as projects_router
from chaima.routers.orders import router as orders_router
from chaima.routers.wishlist import router as wishlist_router
from chaima.routers.suppliers import router as suppliers_router
from chaima.routers.admin_analytics import router as admin_analytics_router
from chaima.schemas import UserRead, UserUpdate
from chaima.middleware.slow_request import SlowRequestMiddleware
from chaima.services.gestis import preload_index
from chaima.services.seed import run_seeds

logger = logging.getLogger(__name__)


def _check_secure_config() -> None:
    """Warn loudly when shipped default secrets are still in use.

    Raises
    ------
    RuntimeError
        If ``CHAIMA_REQUIRE_SECURE_CONFIG`` is enabled while a default
        secret is still active, refusing to start.
    """
    insecure: list[str] = []
    if settings.secret_key.get_secret_value() == DEFAULT_SECRET_KEY:
        insecure.append("CHAIMA_SECRET_KEY")
    if admin_settings.admin_password.get_secret_value() == DEFAULT_ADMIN_PASSWORD:
        insecure.append("CHAIMA_ADMIN_PASSWORD")
    if not insecure:
        return
    message = (
        "SECURITY: default values still in use for %s — set these environment "
        "variables before exposing this instance to a network."
    )
    logger.warning(message, ", ".join(insecure))
    if settings.require_secure_config:
        raise RuntimeError(
            "Refusing to start: CHAIMA_REQUIRE_SECURE_CONFIG is enabled but "
            f"default values are still in use for {', '.join(insecure)}."
        )


def _run_migrations() -> None:
    """Run ``alembic upgrade head`` programmatically.

    Called via ``asyncio.to_thread`` because ``alembic/env.py`` starts its
    own event loop (``asyncio.run``), which must not nest inside ours.
    Falls back to ``create_all`` when the migration scripts are not present
    (e.g. installed as a wheel without the repo checkout).
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig

    script_location = Path(__file__).resolve().parents[2] / "alembic"
    if not (script_location / "env.py").is_file():
        logger.warning(
            "Alembic scripts not found at %s — falling back to create_all "
            "(schema will not be version-stamped).",
            script_location,
        )
        asyncio.run(create_db_and_tables())
        return

    # A bare Config (no ini file) skips env.py's fileConfig() call, which
    # would otherwise clobber uvicorn's logging setup; env.py supplies the
    # database URL itself from chaima.config.settings.
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(script_location))
    command.upgrade(cfg, "head")


async def seed_admin(session: AsyncSession) -> None:
    """Create the initial superuser and group if no superuser exists.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    """
    from fastapi_users.password import PasswordHelper

    result = await session.exec(select(User).where(User.is_superuser == True))
    if result.first() is not None:
        return

    # Reuse an existing group of the same name (e.g. left over from a
    # previous install) instead of crashing on the unique constraint.
    result = await session.exec(
        select(Group).where(Group.name == admin_settings.admin_group_name)
    )
    group = result.first()
    if group is None:
        group = Group(name=admin_settings.admin_group_name)
        session.add(group)
        await session.flush()

    ph = PasswordHelper()
    user = User(
        email=admin_settings.admin_email,
        hashed_password=ph.hash(admin_settings.admin_password.get_secret_value()),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(user)
    await session.flush()

    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_secure_config()
    await asyncio.to_thread(_run_migrations)
    async with async_session_maker() as session:
        await seed_admin(session)
        await run_seeds(session)
    # Background pre-load of the GESTIS CAS→ZVG index (~8,740 entries, one
    # request). Never blocks startup; failures degrade to on-demand loads.
    preload_task = asyncio.create_task(preload_index())
    yield
    preload_task.cancel()


app = FastAPI(title="ChAIMa", lifespan=lifespan)
app.add_middleware(SlowRequestMiddleware, threshold_ms=500)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/v1/auth/cookie",
    tags=["auth"],
)
app.include_router(users_custom_router)
app.include_router(password_reset_router)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/v1/users",
    tags=["users"],
)
app.include_router(groups_router)
app.include_router(ghs_router)
app.include_router(suppliers_router)
app.include_router(projects_router)
app.include_router(orders_router)
app.include_router(wishlist_router)
app.include_router(storage_locations_router)
app.include_router(hazard_tags_router)
app.include_router(chemicals_router)
app.include_router(containers_router)
app.include_router(invites_router)
app.include_router(pubchem_router)
app.include_router(import_router)
app.include_router(compatibility_router)
app.include_router(admin_analytics_router)

# Serve built frontend assets when available (after `uv build` or `vite build`).
# During development the Vite dev server proxies /api to this backend instead.
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"))

from chaima.services.files import UPLOADS_ROOT

if UPLOADS_ROOT.is_dir() or UPLOADS_ROOT.parent.is_dir():
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    # StaticFiles performs its own path-containment check, so traversal
    # attempts against /uploads are rejected by Starlette itself.
    app.mount("/uploads", StaticFiles(directory=UPLOADS_ROOT))

if _static_dir.is_dir():
    _static_root = _static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa_catch_all(path: str) -> FileResponse:
        """Serve real static files when they exist, else fall back to the SPA.

        Parameters
        ----------
        path : str
            The requested path, relative to the static directory.

        Returns
        -------
        FileResponse
            The matching file under ``_static_dir`` when it exists (e.g.
            ``/favicon.svg``, ``/icons.svg``), otherwise ``index.html`` so
            the SPA router can handle client-side routes.

        Raises
        ------
        HTTPException
            404 when no frontend build (``index.html``) is present.
        """
        try:
            static_file = (_static_root / path).resolve()
        except (OSError, ValueError):
            static_file = None
        # Containment check: never serve anything that resolves outside the
        # static dir (e.g. `GET /..%2f..%2fchaima.db` path traversal).
        if (
            static_file is not None
            and static_file.is_relative_to(_static_root)
            and static_file.is_file()
        ):
            return FileResponse(static_file)
        index_file = _static_root / "index.html"
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(index_file)

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.staticfiles import StaticFiles

from chaima.auth import auth_backend, fastapi_users
from chaima.config import admin_settings
from chaima.db import async_session_maker, create_db_and_tables
from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User
from chaima.routers.chemicals import router as chemicals_router
from chaima.routers.pubchem import router as pubchem_router
from chaima.routers.containers import router as containers_router
from chaima.routers.ghs import router as ghs_router
from chaima.routers.groups import router as groups_router
from chaima.routers.users import router as users_custom_router
from chaima.routers.hazard_tags import router as hazard_tags_router
from chaima.routers.invites import router as invites_router
from chaima.routers.storage_locations import router as storage_locations_router
from chaima.routers.import_ import router as import_router
from chaima.routers.suppliers import router as suppliers_router
from chaima.schemas import UserRead, UserUpdate
from chaima.services.seed import run_seeds


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
    await create_db_and_tables()
    async with async_session_maker() as session:
        await seed_admin(session)
        await run_seeds(session)
    yield


app = FastAPI(title="ChAIMa", lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/v1/auth/cookie",
    tags=["auth"],
)
app.include_router(users_custom_router)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/v1/users",
    tags=["users"],
)
app.include_router(groups_router)
app.include_router(ghs_router)
app.include_router(suppliers_router)
app.include_router(storage_locations_router)
app.include_router(hazard_tags_router)
app.include_router(chemicals_router)
app.include_router(containers_router)
app.include_router(invites_router)
app.include_router(pubchem_router)
app.include_router(import_router)

# Serve built frontend assets when available (after `uv build` or `vite build`).
# During development the Vite dev server proxies /api to this backend instead.
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"))

from chaima.services.files import UPLOADS_ROOT

if UPLOADS_ROOT.is_dir() or UPLOADS_ROOT.parent.is_dir():
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOADS_ROOT))

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
        """
        static_file = _static_dir / path
        if static_file.is_file():
            return FileResponse(static_file)
        return FileResponse(_static_dir / "index.html")

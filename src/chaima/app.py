from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from chaima.auth import auth_backend, fastapi_users
from chaima.db import create_db_and_tables
from chaima.routers.chemicals import router as chemicals_router
from chaima.routers.containers import router as containers_router
from chaima.routers.ghs import router as ghs_router
from chaima.routers.groups import router as groups_router
from chaima.routers.hazard_tags import router as hazard_tags_router
from chaima.routers.storage_locations import router as storage_locations_router
from chaima.routers.suppliers import router as suppliers_router
from chaima.schemas import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(title="ChAIMa", lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/v1/auth/cookie",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/v1/auth",
    tags=["auth"],
)
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

# Serve built frontend assets when available (after `uv build` or `vite build`).
# During development the Vite dev server proxies /api to this backend instead.
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"))

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa_catch_all(path: str) -> FileResponse:  # noqa: ARG001
        return FileResponse(_static_dir / "index.html")

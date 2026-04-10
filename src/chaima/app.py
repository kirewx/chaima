from contextlib import asynccontextmanager

from fastapi import FastAPI

from chaima.auth import auth_backend, fastapi_users
from chaima.db import create_db_and_tables
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

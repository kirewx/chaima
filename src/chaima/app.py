from contextlib import asynccontextmanager

from fastapi import FastAPI

from chaima.auth import auth_backend, fastapi_users
from chaima.db import create_db_and_tables
from chaima.schemas import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(title="ChAIMa", lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

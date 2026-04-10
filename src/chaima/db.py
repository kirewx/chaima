from collections.abc import AsyncGenerator

from sqlalchemy.orm import DeclarativeBase
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chaima.config import settings

# Share metadata so fastapi-users (DeclarativeBase) and SQLModel
# models all register in the same metadata. Alembic uses one target.


class Base(DeclarativeBase):
    metadata = SQLModel.metadata


engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

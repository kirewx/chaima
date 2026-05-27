from collections.abc import AsyncGenerator

from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.config import settings

# Share metadata AND registry so fastapi-users (DeclarativeBase) and SQLModel
# models all register in the same metadata and can cross-reference each other.
# Alembic uses one target.


class Base(DeclarativeBase):
    metadata = SQLModel.metadata
    registry = SQLModel._sa_registry


def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    """Apply SQLite pragmas on every new connection.

    WAL mode lets readers and writers operate concurrently; without it,
    an analytics SELECT could briefly block a user-facing INSERT.

    Idempotent: re-running on the same connection is a no-op for journal_mode.
    """
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


engine = create_async_engine(settings.database_url, echo=False)

# Only attach to SQLite engines — Postgres etc. ignore these pragmas anyway,
# but the listener would fail on non-sqlite connections.
if engine.dialect.name == "sqlite":
    sa_event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
        await session.commit()

"""Verify SQLite WAL mode is enabled for the production engine."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from chaima.db import _set_sqlite_pragmas


@pytest.mark.asyncio
async def test_wal_mode_pragma_applied_on_file_engine(tmp_path):
    """When connecting to a real file DB, journal_mode should be WAL."""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    # Attach the same pragma listener the app uses.
    from sqlalchemy import event as sa_event
    sync_engine = engine.sync_engine
    sa_event.listen(sync_engine, "connect", _set_sqlite_pragmas)

    async with engine.connect() as conn:
        result = await conn.exec_driver_sql("PRAGMA journal_mode")
        mode = result.scalar_one()
    await engine.dispose()
    assert mode.lower() == "wal"


def test_pragma_listener_is_idempotent():
    """Calling _set_sqlite_pragmas twice on the same connection should not raise."""
    import sqlite3
    raw = sqlite3.connect(":memory:")
    _set_sqlite_pragmas(raw, None)
    _set_sqlite_pragmas(raw, None)
    raw.close()

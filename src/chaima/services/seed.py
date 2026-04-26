# src/chaima/services/seed.py
"""Idempotent data seeds run from the FastAPI lifespan.

Each seed function must be safe to run on every startup: it may insert
missing rows but must never overwrite existing ones. Add new seeds by
writing an async function and calling it from ``run_seeds``.
"""
import json
import logging
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.ghs import GHSCode

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_GHS_CATALOG_PATH = _DATA_DIR / "ghs_codes.json"


async def seed_ghs_catalog(session: AsyncSession) -> None:
    """Insert missing rows from the GHS catalog.

    Existing rows are left untouched (hand-edited descriptions survive).
    """
    entries = json.loads(_GHS_CATALOG_PATH.read_text())

    existing_codes: set[str] = set()
    result = await session.exec(select(GHSCode.code))
    for code in result.all():
        existing_codes.add(code)

    inserted = 0
    for entry in entries:
        code = entry["code"]
        if code in existing_codes:
            continue
        session.add(
            GHSCode(
                code=code,
                description=entry["description"],
                signal_word=entry.get("signal_word"),
                pictogram=entry.get("pictogram"),
            )
        )
        inserted += 1

    await session.flush()
    await session.commit()
    logger.info(
        "seeded GHS: %d inserted, %d already present",
        inserted,
        len(entries) - inserted,
    )


async def run_seeds(session: AsyncSession) -> None:
    """Run every registered seed in order.

    Called from the FastAPI lifespan after ``create_db_and_tables``.
    """
    await seed_ghs_catalog(session)

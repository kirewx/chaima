# tests/test_services/test_seed.py
import json
from pathlib import Path

from sqlmodel import select

from chaima.models.ghs import GHSCode
from chaima.services.seed import run_seeds, seed_ghs_catalog

CATALOG_PATH = Path("src/chaima/data/ghs_codes.json")


async def test_seed_ghs_catalog_inserts_all(session):
    expected = json.loads(CATALOG_PATH.read_text())

    await seed_ghs_catalog(session)
    await session.commit()

    result = await session.exec(select(GHSCode))
    rows = result.all()
    assert len(rows) == len(expected)
    codes = {r.code for r in rows}
    assert "H225" in codes
    assert "H319" in codes
    assert "EUH066" in codes


async def test_seed_ghs_catalog_idempotent(session):
    await seed_ghs_catalog(session)
    await session.commit()
    first_count = len((await session.exec(select(GHSCode))).all())

    await seed_ghs_catalog(session)
    await session.commit()
    second_count = len((await session.exec(select(GHSCode))).all())

    assert first_count == second_count


async def test_seed_preserves_edited_descriptions(session):
    await seed_ghs_catalog(session)
    await session.commit()

    # Hand-edit an existing row
    row = (
        await session.exec(select(GHSCode).where(GHSCode.code == "H225"))
    ).first()
    assert row is not None
    row.description = "HAND EDITED"
    session.add(row)
    await session.commit()

    # Re-run seed
    await seed_ghs_catalog(session)
    await session.commit()

    row = (
        await session.exec(select(GHSCode).where(GHSCode.code == "H225"))
    ).first()
    assert row is not None
    assert row.description == "HAND EDITED"


async def test_run_seeds_runs_ghs_catalog(session):
    await run_seeds(session)
    await session.commit()
    result = await session.exec(select(GHSCode))
    assert len(result.all()) > 0

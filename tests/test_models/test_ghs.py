import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.chemical import Chemical  # noqa: F401 — ensures table is in metadata
from chaima.models.group import Group  # noqa: F401 — ensures table is in metadata
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.models.user import User  # noqa: F401 — ensures table is in metadata


async def test_create_ghs_code(session):
    code = GHSCode(code="H300", description="Fatal if swallowed", signal_word="Danger")
    session.add(code)
    await session.commit()

    result = await session.get(GHSCode, code.id)
    assert result.code == "H300"
    assert result.description == "Fatal if swallowed"


async def test_ghs_code_unique(session):
    session.add(GHSCode(code="H300", description="Fatal if swallowed"))
    await session.commit()
    session.add(GHSCode(code="H300", description="Duplicate"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_link_chemical_to_ghs(session, chemical):
    h300 = GHSCode(code="H300", description="Fatal if swallowed")
    h310 = GHSCode(code="H310", description="Fatal in contact with skin")
    session.add_all([h300, h310])
    await session.flush()

    session.add_all([
        ChemicalGHS(chemical_id=chemical.id, ghs_id=h300.id),
        ChemicalGHS(chemical_id=chemical.id, ghs_id=h310.id),
    ])
    await session.commit()

    result = (await session.exec(
        select(ChemicalGHS).where(ChemicalGHS.chemical_id == chemical.id)
    )).all()
    assert len(result) == 2

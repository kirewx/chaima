import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.chemical import Chemical  # noqa: F401 — ensures table is in metadata
from chaima.models.group import Group  # noqa: F401 — ensures table is in metadata
from chaima.models.hazard import ChemicalHazardTag, HazardTag, HazardTagIncompatibility
from chaima.models.user import User  # noqa: F401 — ensures table is in metadata


async def test_create_hazard_tag(session):
    tag = HazardTag(name="flammable", description="Catches fire easily")
    session.add(tag)
    await session.commit()

    result = await session.get(HazardTag, tag.id)
    assert result.name == "flammable"


async def test_hazard_tag_name_unique(session):
    session.add(HazardTag(name="flammable"))
    await session.commit()
    session.add(HazardTag(name="flammable"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_link_chemical_to_hazard_tag(session, chemical):
    tag = HazardTag(name="flammable")
    session.add(tag)
    await session.flush()

    session.add(ChemicalHazardTag(chemical_id=chemical.id, hazard_tag_id=tag.id))
    await session.commit()

    result = (await session.exec(
        select(ChemicalHazardTag).where(ChemicalHazardTag.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].hazard_tag_id == tag.id


async def test_incompatibility_pair(session):
    acid = HazardTag(name="acid")
    base = HazardTag(name="base")
    session.add_all([acid, base])
    await session.flush()

    incompat = HazardTagIncompatibility(
        tag_a_id=acid.id,
        tag_b_id=base.id,
        reason="Exothermic neutralization reaction",
    )
    session.add(incompat)
    await session.commit()

    result = await session.get(HazardTagIncompatibility, incompat.id)
    assert result.reason == "Exothermic neutralization reaction"


async def test_incompatibility_pair_unique(session):
    acid = HazardTag(name="acid")
    base = HazardTag(name="base")
    session.add_all([acid, base])
    await session.flush()

    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    await session.commit()
    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    with pytest.raises(IntegrityError):
        await session.commit()

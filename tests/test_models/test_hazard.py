import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.chemical import Chemical  # noqa: F401 — ensures table is in metadata
from chaima.models.group import Group  # noqa: F401 — ensures table is in metadata
from chaima.models.hazard import ChemicalHazardTag, HazardTag, HazardTagIncompatibility
from chaima.models.user import User  # noqa: F401 — ensures table is in metadata


async def test_create_hazard_tag(session, group):
    tag = HazardTag(name="flammable", description="Catches fire easily", group_id=group.id)
    session.add(tag)
    await session.commit()

    result = await session.get(HazardTag, tag.id)
    assert result.name == "flammable"
    assert result.group_id == group.id


async def test_hazard_tag_name_unique_within_group(session, group):
    session.add(HazardTag(name="flammable", group_id=group.id))
    await session.commit()
    session.add(HazardTag(name="flammable", group_id=group.id))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_hazard_tag_name_allowed_across_groups(session):
    group_a = Group(name="Lab Alpha")
    group_b = Group(name="Lab Beta")
    session.add_all([group_a, group_b])
    await session.flush()

    session.add(HazardTag(name="flammable", group_id=group_a.id))
    session.add(HazardTag(name="flammable", group_id=group_b.id))
    await session.commit()

    result = (await session.exec(
        select(HazardTag).where(HazardTag.name == "flammable")
    )).all()
    assert len(result) == 2


async def test_link_chemical_to_hazard_tag(session, chemical, group):
    tag = HazardTag(name="flammable", group_id=group.id)
    session.add(tag)
    await session.flush()

    session.add(ChemicalHazardTag(chemical_id=chemical.id, hazard_tag_id=tag.id))
    await session.commit()

    result = (await session.exec(
        select(ChemicalHazardTag).where(ChemicalHazardTag.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].hazard_tag_id == tag.id


async def test_incompatibility_pair(session, group):
    acid = HazardTag(name="acid", group_id=group.id)
    base = HazardTag(name="base", group_id=group.id)
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


async def test_incompatibility_pair_unique(session, group):
    acid = HazardTag(name="acid", group_id=group.id)
    base = HazardTag(name="base", group_id=group.id)
    session.add_all([acid, base])
    await session.flush()

    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    await session.commit()
    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    with pytest.raises(IntegrityError):
        await session.commit()

# tests/test_services/test_chemicals.py
import pytest

from chaima.models.chemical import Chemical
from chaima.models.ghs import GHSCode
from chaima.models.hazard import HazardTag
from chaima.services import chemicals as chemical_service


async def test_create_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol", cas="64-17-5"
    )
    await session.commit()
    assert chem.name == "Ethanol"
    assert chem.cas == "64-17-5"
    assert chem.group_id == group.id


async def test_list_chemicals(session, group, user):
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Ethanol")
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Methanol")
    await session.commit()
    items, total = await chemical_service.list_chemicals(session, group_id=group.id, viewer=user)
    assert total == 2


async def test_list_chemicals_search(session, group, user):
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Ethanol", cas="64-17-5")
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Acetone")
    await session.commit()
    items, total = await chemical_service.list_chemicals(session, group_id=group.id, viewer=user, search="Ethanol")
    assert total == 1
    assert items[0].name == "Ethanol"


async def test_get_chemical_detail(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    detail = await chemical_service.get_chemical_detail(session, chem.id)
    assert detail is not None
    assert detail.name == "Ethanol"


async def test_update_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    updated = await chemical_service.update_chemical(session, chem, name="Ethanol (abs.)")
    await session.commit()
    assert updated.name == "Ethanol (abs.)"


async def test_replace_synonyms(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()

    synonyms = await chemical_service.replace_synonyms(
        session, chem.id, [{"name": "EtOH", "category": "common"}, {"name": "Ethyl alcohol"}]
    )
    await session.commit()
    assert len(synonyms) == 2

    # Replace again
    synonyms = await chemical_service.replace_synonyms(
        session, chem.id, [{"name": "Alcohol"}]
    )
    await session.commit()
    assert len(synonyms) == 1
    assert synonyms[0].name == "Alcohol"


async def test_replace_ghs_codes(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    ghs1 = GHSCode(code="H225", description="Highly flammable liquid and vapour")
    ghs2 = GHSCode(code="H319", description="Causes serious eye irritation")
    session.add_all([ghs1, ghs2])
    await session.commit()

    codes = await chemical_service.replace_ghs_codes(session, chem.id, [ghs1.id, ghs2.id])
    await session.commit()
    assert len(codes) == 2


async def test_replace_hazard_tags(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    tag = HazardTag(name="flammable", group_id=group.id)
    session.add(tag)
    await session.commit()

    tags = await chemical_service.replace_hazard_tags(
        session, chem.id, group_id=group.id, tag_ids=[tag.id]
    )
    await session.commit()
    assert len(tags) == 1


async def test_replace_hazard_tags_cross_group(session, group, user):
    from chaima.models.group import Group

    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    other_group = Group(name="Other Lab")
    session.add(other_group)
    await session.flush()
    tag = HazardTag(name="flammable", group_id=other_group.id)
    session.add(tag)
    await session.commit()

    with pytest.raises(chemical_service.CrossGroupError):
        await chemical_service.replace_hazard_tags(
            session, chem.id, group_id=group.id, tag_ids=[tag.id]
        )


async def test_delete_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    await chemical_service.delete_chemical(session, chem)
    await session.commit()
    result = await chemical_service.get_chemical(session, chem.id)
    assert result is None

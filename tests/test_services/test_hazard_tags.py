# tests/test_services/test_hazard_tags.py
import pytest

from chaima.services import hazard_tags as hazard_service


async def test_create_hazard_tag(session, group):
    tag = await hazard_service.create_hazard_tag(
        session, group_id=group.id, name="flammable"
    )
    await session.commit()
    assert tag.name == "flammable"
    assert tag.group_id == group.id


async def test_create_hazard_tag_duplicate(session, group):
    await hazard_service.create_hazard_tag(session, group_id=group.id, name="flammable")
    await session.commit()
    with pytest.raises(hazard_service.DuplicateTagError):
        await hazard_service.create_hazard_tag(session, group_id=group.id, name="flammable")


async def test_list_hazard_tags(session, group):
    await hazard_service.create_hazard_tag(session, group_id=group.id, name="flammable")
    await hazard_service.create_hazard_tag(session, group_id=group.id, name="oxidizing")
    await session.commit()
    items, total = await hazard_service.list_hazard_tags(session, group_id=group.id)
    assert total == 2


async def test_create_incompatibility(session, group):
    tag_a = await hazard_service.create_hazard_tag(session, group_id=group.id, name="acid")
    tag_b = await hazard_service.create_hazard_tag(session, group_id=group.id, name="base")
    await session.flush()

    incompat = await hazard_service.create_incompatibility(
        session, group_id=group.id, tag_a_id=tag_a.id, tag_b_id=tag_b.id, reason="Neutralization"
    )
    await session.commit()
    assert incompat.reason == "Neutralization"


async def test_create_incompatibility_different_groups(session, group):
    from chaima.models.group import Group

    other_group = Group(name="Other Lab")
    session.add(other_group)
    await session.flush()

    tag_a = await hazard_service.create_hazard_tag(session, group_id=group.id, name="acid")
    tag_b = await hazard_service.create_hazard_tag(session, group_id=other_group.id, name="base")
    await session.flush()

    with pytest.raises(hazard_service.CrossGroupError):
        await hazard_service.create_incompatibility(
            session, group_id=group.id, tag_a_id=tag_a.id, tag_b_id=tag_b.id
        )


async def test_delete_hazard_tag(session, group):
    tag = await hazard_service.create_hazard_tag(session, group_id=group.id, name="flammable")
    await session.commit()
    await hazard_service.delete_hazard_tag(session, tag)
    await session.commit()
    result = await hazard_service.get_hazard_tag(session, tag.id)
    assert result is None

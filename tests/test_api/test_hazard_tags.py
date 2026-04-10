# tests/test_api/test_hazard_tags.py
from chaima.models.hazard import HazardTag
from chaima.schemas.hazard import HazardTagRead, IncompatibilityRead
from chaima.schemas.pagination import PaginatedResponse


async def test_create_hazard_tag(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/hazard-tags",
        json={"name": "flammable"},
    )
    assert resp.status_code == 201
    result = HazardTagRead.model_validate(resp.json())
    assert result.name == "flammable"


async def test_list_hazard_tags(client, session, group, membership):
    session.add(HazardTag(name="flammable", group_id=group.id))
    session.add(HazardTag(name="oxidizing", group_id=group.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/hazard-tags")
    assert resp.status_code == 200
    page = PaginatedResponse[HazardTagRead].model_validate(resp.json())
    assert page.total == 2


async def test_create_incompatibility(client, session, group, membership):
    tag_a = HazardTag(name="acid", group_id=group.id)
    tag_b = HazardTag(name="base", group_id=group.id)
    session.add(tag_a)
    session.add(tag_b)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/hazard-tags/incompatibilities",
        json={"tag_a_id": str(tag_a.id), "tag_b_id": str(tag_b.id), "reason": "Neutralization"},
    )
    assert resp.status_code == 201
    result = IncompatibilityRead.model_validate(resp.json())
    assert result.reason == "Neutralization"


async def test_create_incompatibility_duplicate(client, session, group, membership):
    tag_a = HazardTag(name="acid", group_id=group.id)
    tag_b = HazardTag(name="base", group_id=group.id)
    session.add(tag_a)
    session.add(tag_b)
    await session.commit()

    await client.post(
        f"/api/v1/groups/{group.id}/hazard-tags/incompatibilities",
        json={"tag_a_id": str(tag_a.id), "tag_b_id": str(tag_b.id)},
    )
    resp = await client.post(
        f"/api/v1/groups/{group.id}/hazard-tags/incompatibilities",
        json={"tag_a_id": str(tag_a.id), "tag_b_id": str(tag_b.id)},
    )
    assert resp.status_code == 409

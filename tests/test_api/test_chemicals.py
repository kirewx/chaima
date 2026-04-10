# tests/test_api/test_chemicals.py
from chaima.models.chemical import Chemical
from chaima.models.ghs import GHSCode
from chaima.models.hazard import HazardTag
from chaima.schemas.chemical import (
    ChemicalDetail,
    ChemicalRead,
    GHSCodeReadNested,
    HazardTagReadNested,
    SynonymRead,
)
from chaima.schemas.pagination import PaginatedResponse


async def test_create_chemical(client, session, group, membership, user):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Ethanol", "cas": "64-17-5"},
    )
    assert resp.status_code == 201
    result = ChemicalRead.model_validate(resp.json())
    assert result.name == "Ethanol"
    assert result.cas == "64-17-5"


async def test_list_chemicals(client, session, group, membership, user):
    session.add(Chemical(group_id=group.id, name="Ethanol", created_by=user.id))
    session.add(Chemical(group_id=group.id, name="Methanol", created_by=user.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals")
    assert resp.status_code == 200
    page = PaginatedResponse[ChemicalRead].model_validate(resp.json())
    assert page.total == 2


async def test_list_chemicals_search(client, session, group, membership, user):
    session.add(Chemical(group_id=group.id, name="Ethanol", created_by=user.id))
    session.add(Chemical(group_id=group.id, name="Acetone", created_by=user.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals?search=Ethanol")
    assert resp.status_code == 200
    page = PaginatedResponse[ChemicalRead].model_validate(resp.json())
    assert page.total == 1


async def test_get_chemical_detail(client, session, group, membership, user):
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(chem)
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals/{chem.id}")
    assert resp.status_code == 200
    detail = ChemicalDetail.model_validate(resp.json())
    assert detail.name == "Ethanol"
    assert isinstance(detail.synonyms, list)
    assert isinstance(detail.ghs_codes, list)
    assert isinstance(detail.hazard_tags, list)


async def test_replace_synonyms(client, session, group, membership, user):
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(chem)
    await session.commit()

    resp = await client.put(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/synonyms",
        json={"synonyms": [{"name": "EtOH", "category": "common"}]},
    )
    assert resp.status_code == 200
    synonyms = [SynonymRead.model_validate(s) for s in resp.json()]
    assert len(synonyms) == 1
    assert synonyms[0].name == "EtOH"


async def test_replace_ghs_codes(client, session, group, membership, user):
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    ghs = GHSCode(code="H225", description="Highly flammable liquid and vapour")
    session.add_all([chem, ghs])
    await session.commit()

    resp = await client.put(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/ghs-codes",
        json={"ghs_ids": [str(ghs.id)]},
    )
    assert resp.status_code == 200
    codes = [GHSCodeReadNested.model_validate(c) for c in resp.json()]
    assert len(codes) == 1


async def test_replace_hazard_tags(client, session, group, membership, user):
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    tag = HazardTag(name="flammable", group_id=group.id)
    session.add_all([chem, tag])
    await session.commit()

    resp = await client.put(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/hazard-tags",
        json={"hazard_tag_ids": [str(tag.id)]},
    )
    assert resp.status_code == 200
    tags = [HazardTagReadNested.model_validate(t) for t in resp.json()]
    assert len(tags) == 1


async def test_create_duplicate_chemical_returns_409(client, session, group, membership, user):
    session.add(Chemical(group_id=group.id, name="Ethanol", created_by=user.id))
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Ethanol"},
    )
    assert resp.status_code == 409


async def test_not_member(client, group):
    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals")
    assert resp.status_code == 403


async def test_chemical_not_found(client, session, group, membership):
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals/{fake_id}")
    assert resp.status_code == 404


async def test_delete_chemical(client, session, group, membership, user):
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(chem)
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/chemicals/{chem.id}")
    assert resp.status_code == 204

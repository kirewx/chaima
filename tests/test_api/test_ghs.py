# tests/test_api/test_ghs.py
from chaima.models.ghs import GHSCode
from chaima.schemas.ghs import GHSCodeRead
from chaima.schemas.pagination import PaginatedResponse


async def test_create_ghs_code(superuser_client):
    resp = await superuser_client.post(
        "/api/v1/ghs-codes",
        json={"code": "H300", "description": "Fatal if swallowed"},
    )
    assert resp.status_code == 201
    result = GHSCodeRead.model_validate(resp.json())
    assert result.code == "H300"


async def test_create_ghs_code_not_superuser(client):
    """Regular user cannot create GHS codes."""
    resp = await client.post(
        "/api/v1/ghs-codes",
        json={"code": "H300", "description": "Fatal if swallowed"},
    )
    assert resp.status_code == 403


async def test_list_ghs_codes(client, session):
    session.add(GHSCode(code="H300", description="Fatal if swallowed"))
    session.add(GHSCode(code="H310", description="Fatal in contact with skin"))
    await session.commit()

    resp = await client.get("/api/v1/ghs-codes")
    assert resp.status_code == 200
    page = PaginatedResponse[GHSCodeRead].model_validate(resp.json())
    assert page.total == 2
    assert len(page.items) == 2


async def test_get_ghs_code(client, session):
    ghs = GHSCode(code="H300", description="Fatal if swallowed")
    session.add(ghs)
    await session.commit()

    resp = await client.get(f"/api/v1/ghs-codes/{ghs.id}")
    assert resp.status_code == 200
    result = GHSCodeRead.model_validate(resp.json())
    assert result.code == "H300"

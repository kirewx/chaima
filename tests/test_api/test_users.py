import pytest


@pytest.mark.asyncio
async def test_user_can_toggle_dark_mode(client, user):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 200
    assert r.json()["dark_mode"] is False

    r = await client.patch("/api/v1/users/me", json={"dark_mode": True})
    assert r.status_code == 200
    assert r.json()["dark_mode"] is True

    r = await client.get("/api/v1/users/me")
    assert r.status_code == 200
    assert r.json()["dark_mode"] is True

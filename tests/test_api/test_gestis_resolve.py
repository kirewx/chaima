from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.models.group import Group


async def test_resolve_hit_persists_zvg(client, session, group, user, membership):
    chem = Chemical(
        name="Ethanol", cas="64-17-5", group_id=group.id, created_by=user.id
    )
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.gestis.get_zvg", AsyncMock(return_value="010420")
    ):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "zvg": "010420",
        "url": "https://gestis-database.dguv.de/data?name=010420",
    }
    await session.refresh(chem)
    assert chem.zvg == "010420"


async def test_resolve_with_stored_zvg_skips_upstream(
    client, session, group, user, membership
):
    chem = Chemical(
        name="Ethanol", cas="64-17-5", zvg="010420",
        group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    mock_get_zvg = AsyncMock()
    with patch("chaima.services.gestis.get_zvg", mock_get_zvg):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json()["zvg"] == "010420"
    mock_get_zvg.assert_not_called()


async def test_resolve_without_cas_returns_nulls(
    client, session, group, user, membership
):
    chem = Chemical(name="Mystery", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    mock_get_zvg = AsyncMock()
    with patch("chaima.services.gestis.get_zvg", mock_get_zvg):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {"zvg": None, "url": None}
    mock_get_zvg.assert_not_called()


async def test_resolve_miss_returns_nulls_persists_nothing(
    client, session, group, user, membership
):
    chem = Chemical(
        name="Cocaine", cas="50-36-2", group_id=group.id, created_by=user.id
    )
    session.add(chem)
    await session.commit()

    with patch("chaima.services.gestis.get_zvg", AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {"zvg": None, "url": None}
    await session.refresh(chem)
    assert chem.zvg is None


async def test_resolve_foreign_group_forbidden(
    client, session, group, user, membership
):
    other_group = Group(name="Lab Beta")
    session.add(other_group)
    await session.flush()
    chem = Chemical(
        name="Ethanol", cas="64-17-5",
        group_id=other_group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{other_group.id}/chemicals/{chem.id}/gestis-resolve"
    )
    assert resp.status_code == 403  # GroupMemberDep: not a member


async def test_resolve_secret_chemical_of_other_user_404(
    client, session, group, user, membership, other_user
):
    chem = Chemical(
        name="Secret stuff", cas="64-17-5", is_secret=True,
        group_id=group.id, created_by=other_user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
    )
    assert resp.status_code == 404

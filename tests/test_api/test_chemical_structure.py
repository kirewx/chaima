"""Tests for the on-demand RDKit structure.svg endpoint."""

from chaima.models.chemical import Chemical


async def test_structure_svg_renders_with_currentcolor(
    client, session, group, membership, user
):
    """A chemical with a valid SMILES returns a themeable SVG."""
    chem = Chemical(
        group_id=group.id,
        name="Ethanol",
        smiles="CCO",
        created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/structure.svg"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.headers["cache-control"] == "public, max-age=3600"
    assert resp.headers["etag"].startswith('W/"')
    body = resp.text
    assert "<svg" in body
    assert "currentColor" in body
    assert "#000000" not in body


async def test_structure_svg_404_when_chemical_has_no_smiles(
    client, session, group, membership, user
):
    """A chemical without SMILES yields 404 with a clear detail."""
    chem = Chemical(
        group_id=group.id,
        name="NoSmiles",
        smiles=None,
        created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/structure.svg"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chemical has no SMILES"


async def test_structure_svg_422_on_invalid_smiles(
    client, session, group, membership, user
):
    """An unparseable SMILES yields 422."""
    chem = Chemical(
        group_id=group.id,
        name="Broken",
        smiles="not-a-real-smiles",
        created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/structure.svg"
    )
    assert resp.status_code == 422


async def test_structure_svg_404_when_chemical_missing(
    client, session, group, membership
):
    """A missing chemical yields 404."""
    from uuid import uuid4

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{uuid4()}/structure.svg"
    )
    assert resp.status_code == 404

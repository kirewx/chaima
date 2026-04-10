# tests/test_api/test_containers.py
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.schemas.container import ContainerRead
from chaima.schemas.pagination import PaginatedResponse


async def _setup(session, group, user):
    """Create test chemical, storage location, and supplier.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group : Group
        The test group.
    user : User
        The test user.

    Returns
    -------
    tuple[Chemical, StorageLocation, Supplier]
        The created test resources.
    """
    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(chem)
    await session.flush()

    loc = StorageLocation(name="Room A")
    session.add(loc)
    await session.flush()
    session.add(StorageLocationGroup(location_id=loc.id, group_id=group.id))

    sup = Supplier(name="Sigma", group_id=group.id)
    session.add(sup)
    await session.commit()
    return chem, loc, sup


async def test_create_container(client, session, group, membership, user):
    """Test creating a container via the nested endpoint."""
    chem, loc, sup = await _setup(session, group, user)

    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/containers",
        json={
            "location_id": str(loc.id),
            "supplier_id": str(sup.id),
            "identifier": "ETH-001",
            "amount": 500.0,
            "unit": "mL",
        },
    )
    assert resp.status_code == 201
    result = ContainerRead.model_validate(resp.json())
    assert result.identifier == "ETH-001"
    assert result.is_archived is False


async def test_list_containers_flat(client, session, group, membership, user):
    """Test listing containers via the flat group endpoint."""
    chem, loc, _ = await _setup(session, group, user)
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, identifier="ETH-001",
        amount=500.0, unit="mL", created_by=user.id,
    ))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/containers")
    assert resp.status_code == 200
    page = PaginatedResponse[ContainerRead].model_validate(resp.json())
    assert page.total == 1


async def test_list_containers_nested(client, session, group, membership, user):
    """Test listing containers via the nested chemical endpoint."""
    chem, loc, _ = await _setup(session, group, user)
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, identifier="ETH-001",
        amount=500.0, unit="mL", created_by=user.id,
    ))
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/containers"
    )
    assert resp.status_code == 200
    page = PaginatedResponse[ContainerRead].model_validate(resp.json())
    assert page.total == 1


async def test_archive_container(client, session, group, membership, user):
    """Test archiving a container and verifying it disappears from the default list."""
    chem, loc, _ = await _setup(session, group, user)
    c = Container(
        chemical_id=chem.id, location_id=loc.id, identifier="ETH-001",
        amount=500.0, unit="mL", created_by=user.id,
    )
    session.add(c)
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/containers/{c.id}")
    assert resp.status_code == 204

    # Should not appear in default list
    resp = await client.get(f"/api/v1/groups/{group.id}/containers")
    page = PaginatedResponse[ContainerRead].model_validate(resp.json())
    assert page.total == 0

    # Should appear in archived list
    resp = await client.get(f"/api/v1/groups/{group.id}/containers?is_archived=true")
    page = PaginatedResponse[ContainerRead].model_validate(resp.json())
    assert page.total == 1


async def test_unarchive_container(client, session, group, membership, user):
    """Test unarchiving a container via PATCH with is_archived: false."""
    chem, loc, _ = await _setup(session, group, user)
    c = Container(
        chemical_id=chem.id, location_id=loc.id, identifier="ETH-001",
        amount=500.0, unit="mL", created_by=user.id, is_archived=True,
    )
    session.add(c)
    await session.commit()

    resp = await client.patch(
        f"/api/v1/groups/{group.id}/containers/{c.id}",
        json={"is_archived": False},
    )
    assert resp.status_code == 200
    result = ContainerRead.model_validate(resp.json())
    assert result.is_archived is False

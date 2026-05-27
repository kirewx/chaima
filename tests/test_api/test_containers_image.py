import io
from pathlib import Path

import pytest
from PIL import Image


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


async def _make_chemical_and_container(client, group_id, tmp_path, monkeypatch):
    """Helper: create a chemical, a storage location, and a container.

    Returns (chemical_id, container_id).
    """
    from chaima.services import files as files_service
    monkeypatch.setattr(files_service, "UPLOADS_ROOT", tmp_path)

    r = await client.post(f"/api/v1/groups/{group_id}/chemicals", json={"name": "X"})
    chem_id = r.json()["id"]

    # Create a storage location at the group root.
    r = await client.post(
        f"/api/v1/groups/{group_id}/storage-locations",
        json={"name": "Shelf A", "kind": "building", "parent_id": None},
    )
    assert r.status_code in (200, 201), r.text
    loc_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/groups/{group_id}/chemicals/{chem_id}/containers",
        json={"identifier": "X-001", "amount": 100, "unit": "mL", "location_id": loc_id},
    )
    assert r.status_code in (200, 201), r.text
    return chem_id, r.json()["id"]


async def test_upload_image_sets_image_path_and_writes_file(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_path"] is not None
    assert body["image_path"].endswith(".jpg")
    saved = tmp_path / body["image_path"]
    assert saved.exists()
    assert saved.read_bytes() == _jpeg()


async def test_upload_image_overwrites_path(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r1 = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    first = r1.json()["image_path"]

    files = {"file": ("b.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r2 = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    second = r2.json()["image_path"]
    assert first != second


async def test_upload_image_rejects_non_image(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("a.txt", io.BytesIO(b"hi"), "text/plain")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 415


async def test_upload_image_404_unknown_container(client, group, membership):
    import uuid
    bogus = uuid.uuid4()
    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{bogus}/image", files=files)
    assert r.status_code == 404


async def test_upload_image_403_for_non_creator_non_admin(
    other_client, session, group, user, membership, other_membership, tmp_path, monkeypatch,
):
    # alice (`user`) creates the container directly via the session so it is
    # owned by alice regardless of which client's auth-override is currently
    # active in app.dependency_overrides.
    from chaima.models.chemical import Chemical
    from chaima.models.container import Container
    from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup
    from chaima.services import files as files_service

    monkeypatch.setattr(files_service, "UPLOADS_ROOT", tmp_path)

    chem = Chemical(group_id=group.id, name="X", created_by=user.id)
    session.add(chem)
    await session.flush()

    loc = StorageLocation(name="Bldg", kind=StorageKind.BUILDING)
    session.add(loc)
    await session.flush()
    session.add(StorageLocationGroup(location_id=loc.id, group_id=group.id))

    cont = Container(
        chemical_id=chem.id,
        location_id=loc.id,
        identifier="X-001",
        amount=100,
        unit="mL",
        created_by=user.id,
    )
    session.add(cont)
    await session.commit()
    cont_id = cont.id

    # bob (other_client, also a member but not admin, not creator) tries to upload
    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await other_client.post(
        f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files,
    )
    assert r.status_code == 403


async def test_upload_image_admin_can_upload_others_containers(
    client, group, user, session, tmp_path, monkeypatch,
):
    from chaima.models.group import UserGroupLink
    # Make alice an admin instead of plain member
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()

    # alice (now admin) creates a chemical + container as before
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)

    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 200

"""Regression tests for the security/correctness fixes on the review branch.

Each test pins a behaviour that was previously broken (crash, 500, or a
cross-group/tenant hole) so it cannot silently regress.
"""

import pytest
from pydantic import SecretStr

from chaima.models.chemical import Chemical
from chaima.models.group import Group
from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup


async def _make_chemical(session, group_id, created_by, name="Acetone"):
    chem = Chemical(group_id=group_id, name=name, created_by=created_by)
    session.add(chem)
    await session.flush()
    return chem


# --------------------------------------------------------------------------
# Startup secure-config guard
# --------------------------------------------------------------------------


def test_secure_config_guard_raises_when_required_and_default(monkeypatch):
    """require_secure_config=True must refuse startup while a default is active."""
    from chaima import app as app_module
    from chaima.config import DEFAULT_SECRET_KEY

    monkeypatch.setattr(app_module.settings, "secret_key", SecretStr(DEFAULT_SECRET_KEY))
    monkeypatch.setattr(app_module.settings, "require_secure_config", True)

    with pytest.raises(RuntimeError, match="Refusing to start"):
        app_module._check_secure_config()


def test_secure_config_guard_passes_with_real_secret(monkeypatch):
    """A non-default secret must let startup proceed even when required."""
    from chaima import app as app_module

    monkeypatch.setattr(app_module.settings, "secret_key", SecretStr("a-real-private-secret"))
    monkeypatch.setattr(app_module.admin_settings, "admin_password", SecretStr("a-real-password"))
    monkeypatch.setattr(app_module.settings, "require_secure_config", True)

    app_module._check_secure_config()  # must not raise


# --------------------------------------------------------------------------
# Cross-group tenant isolation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_group_archive_is_rejected(client, session, user, membership, group):
    """A member of group A cannot archive a chemical belonging to group B."""
    other_group = Group(name="Lab Beta")
    session.add(other_group)
    await session.flush()
    victim = await _make_chemical(session, other_group.id, user.id, name="Ether")

    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{victim.id}/archive"
    )
    assert r.status_code == 404, r.text

    await session.refresh(victim)
    assert victim.is_archived is False


@pytest.mark.asyncio
async def test_compatibility_does_not_leak_other_group(client, session, user, membership, group):
    """Compatibility endpoints must not read another group's location/chemicals."""
    other_group = Group(name="Lab Beta")
    session.add(other_group)
    await session.flush()
    loc = StorageLocation(name="Beta Shelf", kind=StorageKind.SHELF)
    session.add(loc)
    await session.flush()
    session.add(StorageLocationGroup(location_id=loc.id, group_id=other_group.id))
    victim = await _make_chemical(session, other_group.id, user.id, name="Aniline")
    await session.flush()

    # The caller is only a member of `group`, not of other_group.
    r = await client.get(
        f"/api/v1/groups/{group.id}/compatibility/check",
        params={"chemical_id": str(victim.id), "location_id": str(loc.id)},
    )
    assert r.status_code == 404, r.text

    r = await client.get(
        f"/api/v1/groups/{group.id}/locations/{loc.id}/conflicts"
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_duplicate_name_409_does_not_leak_secret(
    other_client, session, user, other_membership, group
):
    """A name collision with another user's secret must not disclose its id."""
    secret = Chemical(
        group_id=group.id, name="Foo", created_by=user.id, is_secret=True
    )
    session.add(secret)
    await session.flush()

    # other_user (not the owner) tries to create a chemical with the same name.
    r = await other_client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Foo"},
    )
    assert r.status_code == 409, r.text
    # The secret's id/archive status must not appear in the error body.
    assert "existing_chemical_id" not in r.text
    assert str(secret.id) not in r.text


@pytest.mark.asyncio
async def test_cross_group_sds_upload_is_rejected(client, session, user, admin_membership, group):
    """An admin of group A cannot overwrite the SDS of group B's chemical."""
    other_group = Group(name="Lab Beta")
    session.add(other_group)
    await session.flush()
    victim = await _make_chemical(session, other_group.id, user.id, name="Toluene")

    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{victim.id}/sds",
        files={"file": ("evil.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 404, r.text

    await session.refresh(victim)
    assert victim.sds_path is None


# --------------------------------------------------------------------------
# No hard delete: chemicals are only ever soft-deleted (archived)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_endpoint_removed(client, session, user, membership, group):
    """The hard-delete endpoint must not exist; removal is archive-only."""
    chem = await _make_chemical(session, group.id, user.id, name="Hexane")

    r = await client.delete(f"/api/v1/groups/{group.id}/chemicals/{chem.id}")
    assert r.status_code == 405, r.text  # Method Not Allowed

    assert await session.get(Chemical, chem.id) is not None

    # Archiving is the supported way to remove a chemical from active lists.
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{chem.id}/archive")
    assert r.status_code == 204, r.text
    await session.refresh(chem)
    assert chem.is_archived is True


# --------------------------------------------------------------------------
# Rename collision returns 409, not 500
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_to_existing_name_returns_conflict(client, session, user, membership, group):
    """Renaming a chemical onto an existing name must be 409, not a 500."""
    await _make_chemical(session, group.id, user.id, name="Ethanol")
    other = await _make_chemical(session, group.id, user.id, name="Propanol")

    r = await client.patch(
        f"/api/v1/groups/{group.id}/chemicals/{other.id}",
        json={"name": "Ethanol"},
    )
    assert r.status_code == 409, r.text

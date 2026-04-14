import pytest

from chaima.models.container import Container
from chaima.services.containers import (
    check_identifier_unique_in_group,
    DuplicateIdentifier,
)


async def test_duplicate_identifier_raises(session, chemical, storage_location, user):
    c1 = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="AB01",
        amount=1.0,
        unit="L",
        created_by=user.id,
    )
    session.add(c1)
    await session.commit()

    with pytest.raises(DuplicateIdentifier):
        await check_identifier_unique_in_group(
            session, group_id=chemical.group_id, identifier="AB01"
        )


async def test_unique_identifier_passes(session, chemical, user):
    # No container exists yet — the identifier should be free
    await check_identifier_unique_in_group(
        session, group_id=chemical.group_id, identifier="AB99"
    )


async def test_exclude_container_id_allows_self_update(
    session, chemical, storage_location, user
):
    c1 = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="AB77",
        amount=1.0,
        unit="L",
        created_by=user.id,
    )
    session.add(c1)
    await session.commit()
    await session.refresh(c1)

    # Updating the same container with the same identifier must not raise
    await check_identifier_unique_in_group(
        session,
        group_id=chemical.group_id,
        identifier="AB77",
        exclude_container_id=c1.id,
    )

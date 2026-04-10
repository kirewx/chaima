from chaima.models.group import Group  # noqa: F401 - ensures table is registered before create_all
from chaima.models.supplier import Supplier


async def test_create_supplier(session, group):
    s = Supplier(name="Sigma Aldrich", group_id=group.id)
    session.add(s)
    await session.commit()

    result = await session.get(Supplier, s.id)
    assert result.name == "Sigma Aldrich"
    assert result.group_id == group.id
    assert result.created_at is not None

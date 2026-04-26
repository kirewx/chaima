import pytest

from chaima.models.wishlist import WishlistStatus
from chaima.services import wishlist as svc


@pytest.mark.asyncio
async def test_create_with_chemical_id(session, group, chemical, user):
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id, comment="please order soon",
    )
    assert item.chemical_id == chemical.id
    assert item.status.value == "open"


@pytest.mark.asyncio
async def test_create_freeform(session, group, user):
    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="Some new reagent", freeform_cas="123-45-6",
        requested_by_user_id=user.id,
    )
    assert item.chemical_id is None
    assert item.freeform_name == "Some new reagent"


@pytest.mark.asyncio
async def test_create_freeform_requires_name(session, group, user):
    with pytest.raises(ValueError):
        await svc.create_wishlist(
            session, group_id=group.id, requested_by_user_id=user.id,
        )


@pytest.mark.asyncio
async def test_dismiss_records_actor_and_timestamp(session, group, chemical, user):
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    await svc.dismiss_wishlist(session, item, dismissed_by_user_id=user.id)
    assert item.status == WishlistStatus.DISMISSED
    assert item.dismissed_at is not None
    assert item.dismissed_by_user_id == user.id


@pytest.mark.asyncio
async def test_promote_already_has_chemical_id(session, group, chemical, user):
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id == chemical.id


@pytest.mark.asyncio
async def test_promote_freeform_creates_chemical_via_pubchem(
    session, group, user, monkeypatch
):
    from chaima.schemas.pubchem import PubChemLookupResult

    async def fake_lookup(query: str) -> PubChemLookupResult:
        return PubChemLookupResult(
            cid="180", name="Acetone", cas="67-64-1",
            molar_mass=58.08, smiles="CC(=O)C",
            synonyms=["acetone", "propan-2-one"], ghs_codes=[],
        )
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="acetone", requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id is not None
    # Verify a Chemical row was created
    from chaima.models.chemical import Chemical
    from sqlmodel import select
    chems = (await session.exec(select(Chemical).where(Chemical.cid == "180"))).all()
    assert len(chems) == 1
    assert chems[0].name == "Acetone"


@pytest.mark.asyncio
async def test_promote_freeform_reuses_existing_chemical_by_cid(
    session, group, user, monkeypatch
):
    from chaima.schemas.pubchem import PubChemLookupResult
    from chaima.models.chemical import Chemical

    existing = Chemical(
        group_id=group.id, name="Acetone", cas="67-64-1", cid="180", created_by=user.id,
    )
    session.add(existing)
    await session.flush()

    async def fake_lookup(query: str) -> PubChemLookupResult:
        return PubChemLookupResult(
            cid="180", name="Acetone", cas="67-64-1",
            molar_mass=58.08, smiles="CC(=O)C",
            synonyms=[], ghs_codes=[],
        )
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id, freeform_name="acetone",
        freeform_cas="67-64-1", requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id == existing.id


@pytest.mark.asyncio
async def test_promote_freeform_no_pubchem_match(session, group, user, monkeypatch):
    from chaima.services.pubchem import PubChemNotFound

    async def fake_lookup(query: str):
        raise PubChemNotFound(query)
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="madeupchem", requested_by_user_id=user.id,
    )
    with pytest.raises(svc.WishlistChemicalNotResolvable):
        await svc.promote_wishlist(session, item)

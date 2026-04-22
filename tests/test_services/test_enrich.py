from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.schemas.pubchem import PubChemLookupResult
from chaima.services import enrich as enrich_service


async def test_enrich_one_fills_only_null_fields(session, group, user):
    chem = Chemical(
        name="Ethanol", cas=None, smiles=None, cid=None, molar_mass=None,
        group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()
    await session.refresh(chem)

    mock_lookup = AsyncMock(return_value=PubChemLookupResult(
        cid="702",
        name="Ethanol",
        cas="64-17-5",
        smiles="CCO",
        molar_mass=46.07,
        synonyms=["ethyl alcohol"],
        ghs_codes=[],
    ))
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
        await session.commit()

    await session.refresh(chem)
    assert result == "enriched"
    assert chem.cid == "702"
    assert chem.smiles == "CCO"
    assert chem.molar_mass == 46.07


async def test_enrich_one_skips_if_cid_set(session, group, user):
    chem = Chemical(
        name="Ethanol", cid="702", group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()
    mock_lookup = AsyncMock()
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
    assert result == "skipped"
    mock_lookup.assert_not_called()


async def test_enrich_one_not_found(session, group, user):
    chem = Chemical(name="Imaginarium", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()
    from chaima.services.pubchem import PubChemNotFound
    mock_lookup = AsyncMock(side_effect=PubChemNotFound("nope"))
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
    assert result == "not_found"

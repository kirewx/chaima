from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult
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


async def test_refetch_ghs_one_skips_without_cid(session, group, user):
    chem = Chemical(name="Mystery", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()
    mock_ghs = AsyncMock()
    mock_syn = AsyncMock()
    with patch("chaima.services.enrich.pubchem_lookup_ghs", mock_ghs), \
         patch("chaima.services.enrich.pubchem_lookup_synonyms", mock_syn):
        result = await enrich_service.refetch_ghs_one(session, chem)
    assert result == "skipped"
    mock_ghs.assert_not_called()
    mock_syn.assert_not_called()


async def test_refetch_ghs_one_adds_codes_and_synonyms(session, group, user):
    session.add(GHSCode(code="H225", description="Highly flammable"))
    session.add(GHSCode(code="H319", description="Eye irritation"))
    chem = Chemical(name="Ethanol", cid="702", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    hits = [
        PubChemGHSHit(code="H225", description="", signal_word=None, pictogram=None),
        PubChemGHSHit(code="H319", description="", signal_word=None, pictogram=None),
    ]
    syns = ["ethyl alcohol", "EtOH"]
    with patch("chaima.services.enrich.pubchem_lookup_ghs", AsyncMock(return_value=hits)), \
         patch("chaima.services.enrich.pubchem_lookup_synonyms", AsyncMock(return_value=syns)):
        result = await enrich_service.refetch_ghs_one(session, chem)
        await session.commit()

    assert result == "updated"
    links = (await session.exec(
        ChemicalGHS.__table__.select().where(ChemicalGHS.chemical_id == chem.id)
    )).all()
    assert len(links) == 2

    from chaima.models.chemical import ChemicalSynonym
    syn_rows = (await session.exec(
        ChemicalSynonym.__table__.select().where(ChemicalSynonym.chemical_id == chem.id)
    )).all()
    syn_names = {row.name for row in syn_rows}
    assert syn_names == {"ethyl alcohol", "EtOH"}


async def test_refetch_ghs_one_merges_synonyms_case_insensitive(session, group, user):
    from chaima.models.chemical import ChemicalSynonym

    chem = Chemical(name="Ethanol", cid="702", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(ChemicalSynonym(chemical_id=chem.id, name="EtOH", category=None))
    await session.commit()

    # PubChem returns "etoh" (different case) and a new one — only the new
    # one should be appended.
    syns = ["etoh", "ethyl alcohol"]
    with patch("chaima.services.enrich.pubchem_lookup_ghs", AsyncMock(return_value=[])), \
         patch("chaima.services.enrich.pubchem_lookup_synonyms", AsyncMock(return_value=syns)):
        result = await enrich_service.refetch_ghs_one(session, chem)
        await session.commit()

    assert result == "updated"
    syn_rows = (await session.exec(
        ChemicalSynonym.__table__.select().where(ChemicalSynonym.chemical_id == chem.id)
    )).all()
    names = [row.name for row in syn_rows]
    assert "EtOH" in names  # original casing preserved
    assert "ethyl alcohol" in names
    assert "etoh" not in names  # not added — duplicate of EtOH


async def test_refetch_ghs_one_unchanged_when_already_present(session, group, user):
    h225 = GHSCode(code="H225", description="Highly flammable")
    session.add(h225)
    chem = Chemical(name="Ethanol", cid="702", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(ChemicalGHS(chemical_id=chem.id, ghs_id=h225.id))
    await session.commit()

    hits = [PubChemGHSHit(code="H225", description="", signal_word=None, pictogram=None)]
    with patch("chaima.services.enrich.pubchem_lookup_ghs", AsyncMock(return_value=hits)), \
         patch("chaima.services.enrich.pubchem_lookup_synonyms", AsyncMock(return_value=[])):
        result = await enrich_service.refetch_ghs_one(session, chem)
    assert result == "unchanged"


async def test_refetch_ghs_one_unchanged_when_pubchem_empty(session, group, user):
    chem = Chemical(name="Ethanol", cid="702", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    with patch("chaima.services.enrich.pubchem_lookup_ghs", AsyncMock(return_value=[])), \
         patch("chaima.services.enrich.pubchem_lookup_synonyms", AsyncMock(return_value=[])):
        result = await enrich_service.refetch_ghs_one(session, chem)
    assert result == "unchanged"

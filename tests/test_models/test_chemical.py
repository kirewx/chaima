from sqlmodel import select

from chaima.models.chemical import Chemical, ChemicalSynonym, StructureSource
from chaima.models.group import Group
from chaima.models.user import User


async def test_create_chemical(session, group, user):
    chem = Chemical(
        group_id=group.id,
        name="Acetone",
        cas="67-64-1",
        smiles="CC(C)=O",
        created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    result = await session.get(Chemical, chem.id)
    assert result is not None
    assert result.name == "Acetone"
    assert result.cas == "67-64-1"
    assert result.group_id == group.id
    assert result.created_by == user.id


async def test_chemical_optional_fields_nullable(session, group, user):
    chem = Chemical(group_id=group.id, name="Water", created_by=user.id)
    session.add(chem)
    await session.commit()

    result = await session.get(Chemical, chem.id)
    assert result.cas is None
    assert result.smiles is None
    assert result.molar_mass is None


async def test_create_synonym_with_category(session, chemical):
    syn = ChemicalSynonym(chemical_id=chemical.id, name="EtOH", category="common")
    session.add(syn)
    await session.commit()

    result = (await session.exec(
        select(ChemicalSynonym).where(ChemicalSynonym.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].name == "EtOH"
    assert result[0].category == "common"


async def test_synonym_category_optional(session, chemical):
    syn = ChemicalSynonym(chemical_id=chemical.id, name="Alcohol")
    session.add(syn)
    await session.commit()

    result = await session.get(ChemicalSynonym, syn.id)
    assert result.category is None


async def test_same_chemical_in_different_groups(session, user):
    g1 = Group(name="Lab X")
    g2 = Group(name="Lab Y")
    session.add_all([g1, g2])
    await session.flush()

    c1 = Chemical(group_id=g1.id, name="Ethanol", created_by=user.id)
    c2 = Chemical(group_id=g2.id, name="Ethanol", created_by=user.id)
    session.add_all([c1, c2])
    await session.commit()

    assert c1.id != c2.id
    assert c1.group_id != c2.group_id


async def test_chemical_defaults_to_not_archived(session, group, user):
    c = Chemical(
        name="Acetone2",
        group_id=group.id,
        created_by=user.id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_archived is False
    assert c.archived_at is None


async def test_chemical_can_be_archived(session, group, user):
    import datetime

    c = Chemical(
        name="Methanol",
        group_id=group.id,
        created_by=user.id,
        is_archived=True,
        archived_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_archived is True
    assert c.archived_at is not None


async def test_chemical_defaults_to_not_secret(session, group, user):
    c = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_secret is False


async def test_chemical_can_be_marked_secret(session, group, user):
    c = Chemical(name="AZ Int 3a", group_id=group.id, created_by=user.id, is_secret=True)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_secret is True


async def test_chemical_structure_source_defaults_to_none(session, group, user):
    c = Chemical(name="Toluene", group_id=group.id, created_by=user.id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.structure_source == StructureSource.NONE
    assert c.sds_path is None


async def test_chemical_structure_source_set_to_pubchem(session, group, user):
    c = Chemical(
        name="Benzene",
        group_id=group.id,
        created_by=user.id,
        structure_source=StructureSource.PUBCHEM,
        sds_path="uploads/g1/benz-sds.pdf",
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.structure_source == StructureSource.PUBCHEM
    assert c.sds_path == "uploads/g1/benz-sds.pdf"

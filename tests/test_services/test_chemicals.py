# tests/test_services/test_chemicals.py
import pytest
from sqlalchemy.orm import selectinload
from sqlmodel import select

from chaima.models.chemical import Chemical
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.models.hazard import HazardTag
from chaima.services import chemicals as chemical_service
from chaima.services.seed import seed_ghs_catalog


async def test_create_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol", cas="64-17-5"
    )
    await session.commit()
    assert chem.name == "Ethanol"
    assert chem.cas == "64-17-5"
    assert chem.group_id == group.id


async def test_list_chemicals(session, group, user):
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Ethanol")
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Methanol")
    await session.commit()
    items, total = await chemical_service.list_chemicals(session, group_id=group.id, viewer=user)
    assert total == 2


async def test_list_chemicals_search(session, group, user):
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Ethanol", cas="64-17-5")
    await chemical_service.create_chemical(session, group_id=group.id, created_by=user.id, name="Acetone")
    await session.commit()
    items, total = await chemical_service.list_chemicals(session, group_id=group.id, viewer=user, search="Ethanol")
    assert total == 1
    assert items[0].name == "Ethanol"


async def test_get_chemical_detail(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    detail = await chemical_service.get_chemical_detail(session, chem.id)
    assert detail is not None
    assert detail.name == "Ethanol"


async def test_update_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    updated = await chemical_service.update_chemical(session, chem, name="Ethanol (abs.)")
    await session.commit()
    assert updated.name == "Ethanol (abs.)"


async def test_replace_synonyms(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()

    synonyms = await chemical_service.replace_synonyms(
        session, chem.id, [{"name": "EtOH", "category": "common"}, {"name": "Ethyl alcohol"}]
    )
    await session.commit()
    assert len(synonyms) == 2

    # Replace again
    synonyms = await chemical_service.replace_synonyms(
        session, chem.id, [{"name": "Alcohol"}]
    )
    await session.commit()
    assert len(synonyms) == 1
    assert synonyms[0].name == "Alcohol"


async def test_replace_ghs_codes(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    ghs1 = GHSCode(code="H225", description="Highly flammable liquid and vapour")
    ghs2 = GHSCode(code="H319", description="Causes serious eye irritation")
    session.add_all([ghs1, ghs2])
    await session.commit()

    codes = await chemical_service.replace_ghs_codes(session, chem.id, [ghs1.id, ghs2.id])
    await session.commit()
    assert len(codes) == 2


async def test_replace_hazard_tags(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    tag = HazardTag(name="flammable", group_id=group.id)
    session.add(tag)
    await session.commit()

    tags = await chemical_service.replace_hazard_tags(
        session, chem.id, group_id=group.id, tag_ids=[tag.id]
    )
    await session.commit()
    assert len(tags) == 1


async def test_replace_hazard_tags_cross_group(session, group, user):
    from chaima.models.group import Group

    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    other_group = Group(name="Other Lab")
    session.add(other_group)
    await session.flush()
    tag = HazardTag(name="flammable", group_id=other_group.id)
    session.add(tag)
    await session.commit()

    with pytest.raises(chemical_service.CrossGroupError):
        await chemical_service.replace_hazard_tags(
            session, chem.id, group_id=group.id, tag_ids=[tag.id]
        )


async def test_delete_chemical(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol"
    )
    await session.commit()
    await chemical_service.delete_chemical(session, chem)
    await session.commit()
    result = await chemical_service.get_chemical(session, chem.id)
    assert result is None


async def test_create_chemical_with_pubchem_payload(session, group, user):
    await seed_ghs_catalog(session)
    await session.commit()

    chem = await chemical_service.create_chemical(
        session,
        group_id=group.id,
        created_by=user.id,
        name="Acetone",
        cas="67-64-1",
        cid="180",
        smiles="CC(=O)C",
        molar_mass=58.08,
        structure_source="pubchem",
        synonyms=["Propan-2-one", "Dimethyl ketone"],
        ghs_codes=["H225", "H319"],
    )
    await session.commit()

    loaded = (
        await session.exec(
            select(Chemical)
            .where(Chemical.id == chem.id)
            .options(
                selectinload(Chemical.synonyms),
                selectinload(Chemical.ghs_links).selectinload(
                    ChemicalGHS.ghs_code
                ),
            )
        )
    ).first()
    assert loaded is not None
    assert loaded.cid == "180"
    assert loaded.molar_mass == 58.08
    names = {s.name for s in loaded.synonyms}
    assert "Propan-2-one" in names
    assert "Dimethyl ketone" in names
    linked_codes = {link.ghs_code.code for link in loaded.ghs_links}
    assert linked_codes == {"H225", "H319"}


async def test_create_chemical_with_unknown_ghs_code_is_skipped(
    session, group, user, caplog
):
    await seed_ghs_catalog(session)
    await session.commit()

    with caplog.at_level("WARNING"):
        chem = await chemical_service.create_chemical(
            session,
            group_id=group.id,
            created_by=user.id,
            name="Mystery compound",
            ghs_codes=["H225", "H999"],
        )
        await session.commit()

    loaded = (
        await session.exec(
            select(Chemical)
            .where(Chemical.id == chem.id)
            .options(
                selectinload(Chemical.ghs_links).selectinload(
                    ChemicalGHS.ghs_code
                )
            )
        )
    ).first()
    assert loaded is not None
    linked = {link.ghs_code.code for link in loaded.ghs_links}
    assert linked == {"H225"}
    assert any("H999" in record.getMessage() for record in caplog.records)


async def test_update_chemical_replaces_synonyms_and_ghs(session, group, user):
    await seed_ghs_catalog(session)
    await session.commit()

    chem = await chemical_service.create_chemical(
        session,
        group_id=group.id,
        created_by=user.id,
        name="Acetone",
        synonyms=["old-synonym"],
        ghs_codes=["H225"],
    )
    await session.commit()

    await chemical_service.update_chemical(
        session,
        chem,
        synonyms=["new-synonym-1", "new-synonym-2"],
        ghs_codes=["H319", "H336"],
    )
    await session.commit()

    loaded = (
        await session.exec(
            select(Chemical)
            .where(Chemical.id == chem.id)
            .options(
                selectinload(Chemical.synonyms),
                selectinload(Chemical.ghs_links).selectinload(
                    ChemicalGHS.ghs_code
                ),
            )
        )
    ).first()
    assert loaded is not None
    assert {s.name for s in loaded.synonyms} == {
        "new-synonym-1",
        "new-synonym-2",
    }
    assert {link.ghs_code.code for link in loaded.ghs_links} == {
        "H319",
        "H336",
    }


async def test_create_chemical_with_pubchem_attaches_image(
    session, group, user, monkeypatch, tmp_path
):
    """If cid + structure_source=pubchem are present, the structure PNG is
    fetched and saved via the files service, populating image_path."""
    from chaima.services import chemicals as chemical_service
    from chaima.services import pubchem as pubchem_service
    from chaima.services import files as files_service

    fake_png = b"\x89PNG\r\n\x1a\nfake-content"

    async def fake_fetch(cid: str):
        return fake_png

    monkeypatch.setattr(pubchem_service, "fetch_structure_image", fake_fetch)
    monkeypatch.setattr(files_service, "UPLOADS_ROOT", tmp_path)
    # Also patch the binding chemicals.py imported at module load time.
    import chaima.services.chemicals as chemicals_module
    monkeypatch.setattr(chemicals_module, "save_upload", files_service.save_upload)

    chem = await chemical_service.create_chemical(
        session,
        group_id=group.id,
        created_by=user.id,
        name="Acetone (image test)",
        cid="180",
        structure_source="pubchem",
    )
    await session.commit()

    assert chem.image_path is not None
    assert chem.image_path.endswith(".png")
    saved_file = tmp_path / chem.image_path
    assert saved_file.read_bytes() == fake_png

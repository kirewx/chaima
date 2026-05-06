import json
from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.schemas.pubchem import PubChemLookupResult


async def test_enrich_endpoint_fills_missing(superuser_client, session, group, superuser):
    chem_a = Chemical(name="Ethanol", group_id=group.id, created_by=superuser.id)
    chem_b = Chemical(name="Acetone", group_id=group.id, created_by=superuser.id, cid="180")
    session.add(chem_a)
    session.add(chem_b)
    await session.commit()

    async def fake_lookup(q):
        return PubChemLookupResult(
            cid="702", smiles="CCO", molar_mass=46.07,
            cas="64-17-5", name=q, synonyms=[], ghs_codes=[],
        )

    with patch("chaima.services.enrich.pubchem_lookup", AsyncMock(side_effect=fake_lookup)):
        resp = await superuser_client.post(
            f"/api/v1/groups/{group.id}/chemicals/enrich-pubchem",
            json={"chemical_ids": [str(chem_a.id), str(chem_b.id)]},
        )
    assert resp.status_code == 200
    events = [json.loads(line[len("data: "):])
              for line in resp.text.splitlines() if line.startswith("data: ")]
    statuses = [e.get("status") for e in events if "status" in e]
    assert "enriched" in statuses
    assert "skipped" in statuses
    summary_event = next(e for e in events if "summary" in e)
    assert summary_event["summary"]["enriched"] == 1
    assert summary_event["summary"]["skipped"] == 1


async def test_enrich_endpoint_requires_superuser(client, group, admin_membership):
    """Group admins (non-superuser) are no longer allowed."""
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/enrich-pubchem",
        json={"chemical_ids": None},
    )
    assert resp.status_code == 403


async def test_refetch_ghs_endpoint_requires_superuser(client, group, admin_membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/refetch-ghs",
        json={"chemical_ids": None},
    )
    assert resp.status_code == 403


async def test_refetch_ghs_endpoint_streams_summary(
    superuser_client, session, group, superuser
):
    from chaima.models.ghs import GHSCode
    from chaima.schemas.pubchem import PubChemGHSHit

    session.add(GHSCode(code="H225", description="Highly flammable"))
    chem_with = Chemical(name="Ethanol", cid="702", group_id=group.id, created_by=superuser.id)
    chem_without = Chemical(name="Mystery", group_id=group.id, created_by=superuser.id)
    session.add(chem_with)
    session.add(chem_without)
    await session.commit()

    hits = [PubChemGHSHit(code="H225", description="", signal_word=None, pictogram=None)]
    with patch(
        "chaima.services.enrich.pubchem_lookup_ghs",
        AsyncMock(return_value=hits),
    ), patch(
        "chaima.services.enrich.pubchem_lookup_synonyms",
        AsyncMock(return_value=[]),
    ):
        resp = await superuser_client.post(
            f"/api/v1/groups/{group.id}/chemicals/refetch-ghs",
            json={"chemical_ids": [str(chem_with.id), str(chem_without.id)]},
        )

    assert resp.status_code == 200
    events = [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    statuses = [e["status"] for e in events if "status" in e]
    assert "updated" in statuses
    assert "skipped" in statuses
    summary = next(e for e in events if "summary" in e)["summary"]
    assert summary["updated"] == 1
    assert summary["skipped"] == 1

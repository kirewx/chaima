import json
from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.schemas.pubchem import PubChemLookupResult


async def test_enrich_endpoint_fills_missing(client, session, group, user, admin_membership):
    chem_a = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    chem_b = Chemical(name="Acetone", group_id=group.id, created_by=user.id, cid="180")
    session.add(chem_a)
    session.add(chem_b)
    await session.commit()

    async def fake_lookup(q):
        return PubChemLookupResult(
            cid="702", smiles="CCO", molar_mass=46.07,
            cas="64-17-5", name=q, synonyms=[], ghs_codes=[],
        )

    with patch("chaima.services.enrich.pubchem_lookup", AsyncMock(side_effect=fake_lookup)):
        resp = await client.post(
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


async def test_enrich_endpoint_requires_admin(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/enrich-pubchem",
        json={"chemical_ids": None},
    )
    assert resp.status_code == 403

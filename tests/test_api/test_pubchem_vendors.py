# tests/test_api/test_pubchem_vendors.py
import pytest


@pytest.mark.asyncio
async def test_get_pubchem_vendors_returns_list(client, monkeypatch):
    from chaima.schemas.pubchem import PubChemVendor

    async def fake_lookup(cid: str):
        return [
            PubChemVendor(name="Sigma-Aldrich", url="https://sigmaaldrich.com/p/180"),
            PubChemVendor(name="abcr", url="https://abcr.com/p/180"),
        ]
    monkeypatch.setattr("chaima.services.pubchem.lookup_vendors", fake_lookup)

    resp = await client.get("/api/v1/pubchem/vendors/180")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cid"] == "180"
    assert len(body["vendors"]) == 2

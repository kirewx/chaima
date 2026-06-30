import json
from pathlib import Path

from chaima.services.pubchem import parse_precautionary_codes

_CATALOG = (
    Path(__file__).resolve().parents[1]
    / ".." / "src" / "chaima" / "data" / "p_statements.json"
).resolve()

_FIXTURES = Path(__file__).resolve().parents[0] / "fixtures"


def test_catalog_is_well_formed():
    entries = json.loads(_CATALOG.read_text(encoding="utf-8"))
    assert isinstance(entries, list) and entries
    codes = [e["code"] for e in entries]
    assert len(codes) == len(set(codes)), "duplicate codes in catalog"
    for e in entries:
        assert e["code"].startswith("P")
        assert e["description"].strip()


def test_catalog_covers_acetone_fixture_codes():
    entries = json.loads(_CATALOG.read_text(encoding="utf-8"))
    codes = {e["code"] for e in entries}
    required = {
        "P210", "P233", "P240", "P241", "P242", "P243", "P261",
        "P264+P265", "P271", "P280", "P303+P361+P353", "P304+P340",
        "P305+P351+P338", "P319", "P337+P317", "P370+P378",
        "P403+P233", "P403+P235", "P405", "P501",
    }
    missing = required - codes
    assert not missing, f"catalog missing required P-codes: {sorted(missing)}"


def test_parse_precautionary_codes_from_acetone_fixture():
    data = json.loads((_FIXTURES / "pubchem_acetone_ghs.json").read_text())
    codes = parse_precautionary_codes(data)
    # Single + combination codes are extracted; "and " prefix on the last
    # item is stripped; majority voting across the 3 buckets applies.
    assert "P210" in codes
    assert "P280" in codes
    assert "P305+P351+P338" in codes
    assert "P501" in codes
    # No stray "and"-prefixed or empty tokens.
    assert all(c.startswith("P") and "+" not in c.strip("P0123456789+") for c in codes)
    assert "" not in codes


def test_parse_precautionary_codes_empty_on_no_section():
    assert parse_precautionary_codes({}) == []

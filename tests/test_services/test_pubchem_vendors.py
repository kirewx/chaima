import json
from pathlib import Path

import pytest


def _load_fixture(name: str) -> dict:
    return json.loads(
        (Path(__file__).parent.parent / "fixtures" / "pubchem" / name).read_text()
    )


def test_parse_chemical_vendors_fixture():
    from chaima.services.pubchem import parse_chemical_vendors

    data = _load_fixture("vendors_acetone.json")
    vendors = parse_chemical_vendors(data)

    assert len(vendors) >= 1
    assert all(v.name and v.url for v in vendors)
    # No duplicate URLs
    urls = [v.url for v in vendors]
    assert len(urls) == len(set(urls))


def test_parse_chemical_vendors_empty_returns_empty_list():
    from chaima.services.pubchem import parse_chemical_vendors

    assert parse_chemical_vendors({}) == []
    assert parse_chemical_vendors({"Record": {"Section": []}}) == []

"""Unit tests for the hazard-compatibility rules engine."""
from __future__ import annotations

from chaima.services.hazard_compatibility import (
    Conflict,
    pair_conflicts,
)


def _ghs(code: str, signal: str = "Warning") -> object:
    class C:
        pass
    c = C()
    c.code = code
    c.signal_word = signal
    c.pictogram = code
    return c


def test_flammable_plus_oxidizer_conflict():
    a_codes = [_ghs("GHS02", "Danger")]
    b_codes = [_ghs("GHS03", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Acetone",
        b_codes=b_codes, b_tags=[], b_name="Hydrogen peroxide",
    )
    assert any(c.kind == "ghs" and "GHS02" in c.code_or_tag for c in out)
    assert any("oxidizer" in (c.reason or "").lower() for c in out)


def test_acid_plus_base_corrosive_conflict():
    a_codes = [_ghs("GHS05", "Danger")]
    b_codes = [_ghs("GHS05", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Hydrochloric acid",
        b_codes=b_codes, b_tags=[], b_name="Sodium hydroxide",
    )
    assert any(c.kind == "ghs" and "corrosive" in (c.reason or "").lower() for c in out)


def test_unrelated_chemicals_no_conflict():
    a_codes = [_ghs("GHS07", "Warning")]
    b_codes = [_ghs("GHS09", "Warning")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Sucrose",
        b_codes=b_codes, b_tags=[], b_name="Sodium chloride",
    )
    assert out == []


def test_explosive_plus_flammable_conflict():
    a_codes = [_ghs("GHS01", "Danger")]
    b_codes = [_ghs("GHS02", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="TNT",
        b_codes=b_codes, b_tags=[], b_name="Acetone",
    )
    assert len(out) >= 1
    assert any(c.kind == "ghs" for c in out)


def test_returns_conflict_dataclass_shape():
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=[_ghs("GHS02", "Danger")],
        a_tags=[],
        a_name="A",
        b_codes=[_ghs("GHS03", "Danger")],
        b_tags=[],
        b_name="B",
    )
    assert isinstance(out[0], Conflict)
    assert out[0].chem_a_name == "A"
    assert out[0].chem_b_name == "B"
    assert out[0].kind in {"ghs", "tag"}

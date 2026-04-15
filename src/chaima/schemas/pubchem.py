# src/chaima/schemas/pubchem.py
"""Schemas for the PubChem lookup endpoint response."""
from pydantic import BaseModel


class PubChemGHSHit(BaseModel):
    """One GHS hazard statement parsed from a PubChem classification.

    Parameters
    ----------
    code : str
        GHS hazard statement code, e.g. ``"H225"``.
    description : str
        Human-readable description of the hazard.
    signal_word : str or None
        ``"Danger"``, ``"Warning"``, or ``None``.
    pictogram : str or None
        Pictogram identifier (``GHS01``–``GHS09``) or ``None``.
    """

    code: str
    description: str
    signal_word: str | None = None
    pictogram: str | None = None


class PubChemLookupResult(BaseModel):
    """Normalized PubChem lookup result returned to the frontend.

    Parameters
    ----------
    cid : str
        PubChem compound ID as a string.
    name : str
        IUPAC name of the compound (preferred display name).
    cas : str or None
        First CAS-pattern synonym found in the synonym list, if any.
    molar_mass : float or None
        Molecular weight in g/mol.
    smiles : str or None
        Canonical SMILES notation.
    synonyms : list[str]
        Up to 20 synonyms (common names, trade names, CAS).
    ghs_codes : list[PubChemGHSHit]
        GHS hazard statements parsed from the PubChem classification.
    """

    cid: str
    name: str
    cas: str | None = None
    molar_mass: float | None = None
    smiles: str | None = None
    synonyms: list[str]
    ghs_codes: list[PubChemGHSHit]

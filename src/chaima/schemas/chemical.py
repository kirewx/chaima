# src/chaima/schemas/chemical.py
import datetime
from uuid import UUID

from pydantic import BaseModel


class ChemicalCreate(BaseModel):
    """Schema for creating a chemical.

    Parameters
    ----------
    name : str
        The name of the chemical (required).
    cas : str or None, optional
        CAS registry number.
    smiles : str or None, optional
        SMILES notation.
    cid : str or None, optional
        PubChem compound ID.
    structure : str or None, optional
        Structure data (e.g. molfile).
    molar_mass : float or None, optional
        Molar mass in g/mol.
    density : float or None, optional
        Density in g/mL.
    melting_point : float or None, optional
        Melting point in degrees Celsius.
    boiling_point : float or None, optional
        Boiling point in degrees Celsius.
    comment : str or None, optional
        Free-text comment.
    """

    name: str
    cas: str | None = None
    smiles: str | None = None
    cid: str | None = None
    structure: str | None = None
    molar_mass: float | None = None
    density: float | None = None
    melting_point: float | None = None
    boiling_point: float | None = None
    comment: str | None = None


class ChemicalUpdate(BaseModel):
    """Schema for partial update of a chemical.

    All fields are optional.
    """

    name: str | None = None
    cas: str | None = None
    smiles: str | None = None
    cid: str | None = None
    structure: str | None = None
    molar_mass: float | None = None
    density: float | None = None
    melting_point: float | None = None
    boiling_point: float | None = None
    comment: str | None = None


class SynonymRead(BaseModel):
    """Schema for reading a chemical synonym.

    Parameters
    ----------
    id : UUID
        Synonym ID.
    name : str
        Synonym name.
    category : str or None
        Optional category label.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    category: str | None


class SynonymWrite(BaseModel):
    """Schema for writing a chemical synonym.

    Parameters
    ----------
    name : str
        Synonym name.
    category : str or None, optional
        Optional category label.
    """

    name: str
    category: str | None = None


class SynonymBulkUpdate(BaseModel):
    """Schema for bulk-replacing synonyms.

    Parameters
    ----------
    synonyms : list[SynonymWrite]
        New synonym list (replaces existing).
    """

    synonyms: list[SynonymWrite]


class GHSCodeBulkUpdate(BaseModel):
    """Schema for bulk-replacing GHS code assignments.

    Parameters
    ----------
    ghs_ids : list[UUID]
        New list of GHS code IDs (replaces existing).
    """

    ghs_ids: list[UUID]


class HazardTagBulkUpdate(BaseModel):
    """Schema for bulk-replacing hazard tag assignments.

    Parameters
    ----------
    hazard_tag_ids : list[UUID]
        New list of hazard tag IDs (replaces existing).
    """

    hazard_tag_ids: list[UUID]


class GHSCodeReadNested(BaseModel):
    """Nested GHS code schema used inside ChemicalDetail.

    Parameters
    ----------
    id : UUID
        GHS code ID.
    code : str
        GHS code string (e.g. H225).
    description : str
        Human-readable description.
    pictogram : str or None
        Pictogram identifier.
    signal_word : str or None
        Signal word (e.g. Danger, Warning).
    """

    model_config = {"from_attributes": True}

    id: UUID
    code: str
    description: str
    pictogram: str | None
    signal_word: str | None


class HazardTagReadNested(BaseModel):
    """Nested hazard tag schema used inside ChemicalDetail.

    Parameters
    ----------
    id : UUID
        Hazard tag ID.
    name : str
        Tag name.
    description : str or None
        Optional description.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None


class ChemicalRead(BaseModel):
    """Schema for reading a chemical (flat, no sub-resources).

    Parameters
    ----------
    id : UUID
        Chemical ID.
    name : str
        Chemical name.
    cas : str or None
        CAS registry number.
    smiles : str or None
        SMILES notation.
    cid : str or None
        PubChem compound ID.
    structure : str or None
        Structure data.
    molar_mass : float or None
        Molar mass in g/mol.
    density : float or None
        Density in g/mL.
    melting_point : float or None
        Melting point in °C.
    boiling_point : float or None
        Boiling point in °C.
    image_path : str or None
        Path to structure image.
    comment : str or None
        Free-text comment.
    created_by : UUID
        ID of the user who created this chemical.
    created_at : datetime.datetime
        Creation timestamp.
    updated_at : datetime.datetime
        Last update timestamp.
    """

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    cas: str | None
    smiles: str | None
    cid: str | None
    structure: str | None
    molar_mass: float | None
    density: float | None
    melting_point: float | None
    boiling_point: float | None
    image_path: str | None
    comment: str | None
    created_by: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ChemicalDetail(ChemicalRead):
    """Extended chemical schema with sub-resource lists.

    Inherits all fields from ChemicalRead and adds synonyms,
    GHS codes, and hazard tags.

    Parameters
    ----------
    synonyms : list[SynonymRead]
        All synonyms for this chemical.
    ghs_codes : list[GHSCodeReadNested]
        GHS codes assigned to this chemical.
    hazard_tags : list[HazardTagReadNested]
        Hazard tags assigned to this chemical.
    """

    synonyms: list[SynonymRead]
    ghs_codes: list[GHSCodeReadNested]
    hazard_tags: list[HazardTagReadNested]

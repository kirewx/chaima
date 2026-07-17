import uuid

from chaima.models.chemical import Chemical
from chaima.schemas.chemical import ChemicalCreate, ChemicalRead, ChemicalUpdate


def test_chemical_model_has_nullable_zvg():
    chem = Chemical(name="Ethanol", group_id=uuid.uuid4(), created_by=uuid.uuid4())
    assert chem.zvg is None


def test_zvg_is_read_only_in_api_schemas():
    # Server-authoritative: exposed on reads, never accepted on writes.
    assert "zvg" in ChemicalRead.model_fields
    assert "zvg" not in ChemicalCreate.model_fields
    assert "zvg" not in ChemicalUpdate.model_fields

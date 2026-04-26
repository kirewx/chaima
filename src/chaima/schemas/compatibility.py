from __future__ import annotations

from pydantic import BaseModel


class ConflictRead(BaseModel):
    chem_a_name: str
    chem_b_name: str
    kind: str
    code_or_tag: str
    reason: str

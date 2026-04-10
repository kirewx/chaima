import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class GHSCode(SQLModel, table=True):
    __tablename__ = "ghs_code"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: str
    pictogram: str | None = Field(default=None)
    signal_word: str | None = Field(default=None)


class ChemicalGHS(SQLModel, table=True):
    __tablename__ = "chemical_ghs"
    __table_args__ = (UniqueConstraint("chemical_id", "ghs_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    ghs_id: uuid_pkg.UUID = Field(foreign_key="ghs_code.id", primary_key=True)

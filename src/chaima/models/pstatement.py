import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class PStatement(SQLModel, table=True):
    __tablename__ = "p_statement"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: str

    chemical_links: list["ChemicalPStatement"] = Relationship(
        back_populates="p_statement"
    )


class ChemicalPStatement(SQLModel, table=True):
    __tablename__ = "chemical_p_statement"
    __table_args__ = (UniqueConstraint("chemical_id", "p_statement_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    p_statement_id: uuid_pkg.UUID = Field(
        foreign_key="p_statement.id", primary_key=True
    )

    chemical: "Chemical" = Relationship(back_populates="pstatement_links")
    p_statement: "PStatement" = Relationship(back_populates="chemical_links")

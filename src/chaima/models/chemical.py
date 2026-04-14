import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class Chemical(SQLModel, table=True):
    __tablename__ = "chemical"
    __table_args__ = (UniqueConstraint("name", "group_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    cas: str | None = Field(default=None, index=True)
    smiles: str | None = Field(default=None)
    cid: str | None = Field(default=None)
    structure: str | None = Field(default=None)
    molar_mass: float | None = Field(default=None)
    density: float | None = Field(default=None)
    melting_point: float | None = Field(default=None)
    boiling_point: float | None = Field(default=None)
    image_path: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )
    is_archived: bool = Field(default=False, index=True)
    is_secret: bool = Field(default=False, index=True)
    archived_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    group: "Group" = Relationship(back_populates="chemicals")
    creator: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Chemical.created_by"}
    )
    synonyms: list["ChemicalSynonym"] = Relationship(back_populates="chemical")
    ghs_links: list["ChemicalGHS"] = Relationship(back_populates="chemical")
    hazard_tag_links: list["ChemicalHazardTag"] = Relationship(back_populates="chemical")
    containers: list["Container"] = Relationship(back_populates="chemical")


class ChemicalSynonym(SQLModel, table=True):
    __tablename__ = "chemical_synonym"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    name: str
    category: str | None = Field(default=None)

    chemical: "Chemical" = Relationship(back_populates="synonyms")

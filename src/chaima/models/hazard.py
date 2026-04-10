import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class HazardTag(SQLModel, table=True):
    __tablename__ = "hazard_tag"
    __table_args__ = (UniqueConstraint("name", "group_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None)

    group: "Group" = Relationship(back_populates="hazard_tags")
    chemical_links: list["ChemicalHazardTag"] = Relationship(back_populates="hazard_tag")


class ChemicalHazardTag(SQLModel, table=True):
    __tablename__ = "chemical_hazard_tag"
    __table_args__ = (UniqueConstraint("chemical_id", "hazard_tag_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    hazard_tag_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id", primary_key=True)

    chemical: "Chemical" = Relationship(back_populates="hazard_tag_links")
    hazard_tag: "HazardTag" = Relationship(back_populates="chemical_links")


class HazardTagIncompatibility(SQLModel, table=True):
    __tablename__ = "hazard_tag_incompatibility"
    __table_args__ = (UniqueConstraint("tag_a_id", "tag_b_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    tag_a_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id")
    tag_b_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id")
    reason: str | None = Field(default=None)

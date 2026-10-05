from __future__ import annotations

import uuid
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.audit import AuditColumns
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.parcel import Parcel


class BuildingType(PyEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    INDUSTRIAL = "industrial"
    INSTITUTIONAL = "institutional"


class ConstructionStatus(PyEnum):
    PLANNED = "planned"
    UNDER_CONSTRUCTION = "under_construction"
    COMPLETED = "completed"
    DEMOLISHED = "demolished"


class Building(BaseModel, AuditColumns):
    __tablename__ = "buildings"

    parcel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    building_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    building_type: Mapped[BuildingType] = mapped_column(
        Enum(
            BuildingType,
            name="building_type",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    construction_status: Mapped[ConstructionStatus] = mapped_column(
        Enum(
            ConstructionStatus,
            name="construction_status",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    footprint_geometry: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False),
        nullable=True,
    )

    parcel: Mapped[Parcel] = relationship(back_populates="buildings")
    floors: Mapped[list[Floor]] = relationship(
        back_populates="building",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

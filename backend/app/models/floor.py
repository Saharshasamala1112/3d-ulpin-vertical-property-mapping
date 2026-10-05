from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.audit import AuditColumns
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.unit import Unit


class FloorType(PyEnum):
    BASEMENT = "basement"
    GROUND = "ground"
    TYPICAL = "typical"
    PENTHOUSE = "penthouse"
    ROOFTOP = "rooftop"


class Floor(BaseModel, AuditColumns):
    __tablename__ = "floors"

    building_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    floor_type: Mapped[FloorType] = mapped_column(
        Enum(
            FloorType,
            name="floor_type",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    elevation_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    elevation_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    building: Mapped[Building] = relationship(back_populates="floors")
    units: Mapped[list[Unit]] = relationship(
        back_populates="floor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

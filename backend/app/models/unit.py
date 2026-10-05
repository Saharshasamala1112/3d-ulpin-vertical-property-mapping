from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.audit import AuditColumns
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.geometry3d import PropertyGeometry


class UnitType(PyEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    PARKING = "parking"
    STORAGE = "storage"
    COMMON_AREA = "common_area"


class UnitStatus(PyEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    SOLD = "sold"
    LEASED = "leased"
    ARCHIVED = "archived"


class Unit(BaseModel, AuditColumns):
    __tablename__ = "units"

    floor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(
        Enum(
            UnitType,
            name="unit_type",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    area_sqm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[UnitStatus] = mapped_column(
        Enum(
            UnitStatus,
            name="unit_status",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    vdc_code: Mapped[str | None] = mapped_column(String(255), nullable=True)

    floor: Mapped[Floor] = relationship(back_populates="units")
    geometry: Mapped[PropertyGeometry | None] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

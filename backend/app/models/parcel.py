from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base

Base = declarative_base()


class ParcelStatus(PyEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_identifier: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    ulpin: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    area_sqm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[ParcelStatus] = mapped_column(
        Enum(ParcelStatus, name="parcel_status", native_enum=False),
        nullable=False,
        default=ParcelStatus.DRAFT,
    )
    parcel_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ulpin_record: Mapped["ULPIN"] = relationship(back_populates="parcel", uselist=False)

    __table_args__ = (
        Index("ix_parcels_ulpin", "ulpin"),
    )


class ULPIN(Base):
    __tablename__ = "ulpins"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    ulpin_code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    issued_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    parcel: Mapped[Parcel] = relationship(back_populates="ulpin_record")

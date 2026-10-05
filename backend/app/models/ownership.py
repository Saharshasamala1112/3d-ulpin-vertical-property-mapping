from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.parcel import Parcel
    from app.models.unit import Unit


class OwnerKind(PyEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class OwnershipStatus(PyEnum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REVOKED = "revoked"


class Owner(BaseModel):
    __tablename__ = "owners"

    kind: Mapped[OwnerKind] = mapped_column(
        Enum(
            OwnerKind,
            name="owner_kind",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    interests: Mapped[list[OwnershipInterest]] = relationship(back_populates="owner")


class OwnershipInterest(BaseModel):
    __tablename__ = "ownership_interests"
    __table_args__ = (
        # Spelled the way PostgreSQL stores these expressions: it drops the
        # redundant parentheses and rewrites BETWEEN as two comparisons, so any
        # other spelling reflects back as different constraint text.
        CheckConstraint(
            "parcel_id IS NOT NULL AND unit_id IS NULL "
            "OR parcel_id IS NULL AND unit_id IS NOT NULL",
            name="ck_ownership_interests_exactly_one_subject",
        ),
        CheckConstraint(
            "share_basis_points >= 1 AND share_basis_points <= 10000",
            name="ck_ownership_interests_share_basis_points",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_ownership_interests_valid_interval",
        ),
        Index("ix_ownership_interests_owner_id", "owner_id"),
        Index(
            "ix_ownership_interests_parcel_effective",
            "parcel_id",
            "valid_from",
            "valid_to",
            postgresql_where="parcel_id IS NOT NULL",
        ),
        Index(
            "ix_ownership_interests_unit_effective",
            "unit_id",
            "valid_from",
            "valid_to",
            postgresql_where="unit_id IS NOT NULL",
        ),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("owners.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parcels.id", ondelete="RESTRICT"),
        nullable=True,
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=True,
    )
    share_basis_points: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[OwnershipStatus] = mapped_column(
        Enum(
            OwnershipStatus,
            name="ownership_status",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=OwnershipStatus.ACTIVE,
    )

    owner: Mapped[Owner] = relationship(back_populates="interests")
    parcel: Mapped[Parcel | None] = relationship()
    unit: Mapped[Unit | None] = relationship()

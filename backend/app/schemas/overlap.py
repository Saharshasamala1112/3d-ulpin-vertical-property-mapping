from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class OverlapGeometry(BaseModel):
    """Axis-aligned bounding box for a computed overlap region."""

    x_min: Decimal
    x_max: Decimal
    y_min: Decimal
    y_max: Decimal
    z_min: Decimal
    z_max: Decimal


class OverlapResult(BaseModel):
    """Volumetric intersection between two property units."""

    unit_a_id: UUID
    unit_b_id: UUID
    overlap_volume: Decimal = Field(gt=0)
    overlap_geometry: OverlapGeometry

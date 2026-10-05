from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

GapDirection = Literal["x", "y", "z"]


class GapGeometry(BaseModel):
    """Axis-aligned bounding box spanning an unoccupied gap region."""

    x_min: Decimal
    x_max: Decimal
    y_min: Decimal
    y_max: Decimal
    z_min: Decimal
    z_max: Decimal


class GapResult(BaseModel):
    """A measured gap between two units along one or more coordinate axes."""

    unit_a_id: UUID
    unit_b_id: UUID
    gap_distance: Decimal = Field(gt=0)
    gap_direction: GapDirection
    gap_geometry: GapGeometry

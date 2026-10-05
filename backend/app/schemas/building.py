from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

_BUILDING_TYPES = r"^(residential|commercial|mixed_use|industrial|institutional)$"
_CONSTRUCTION_STATUSES = r"^(planned|under_construction|completed|demolished)$"


class BuildingCreate(BaseModel):
    """Request body for creating a building under a parcel."""

    building_identifier: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    building_type: str = Field(
        pattern=_BUILDING_TYPES,
        description=(
            "Type of the building (residential, commercial, mixed_use, industrial, institutional)"
        ),
    )
    construction_status: str = Field(
        default="planned",
        pattern=_CONSTRUCTION_STATUSES,
        description=("Construction status (planned, under_construction, completed, demolished)"),
    )
    footprint_geometry: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional GeoJSON Polygon geometry (SRID 4326) for the building footprint. "
            "Deep geometry validation is out of scope."
        ),
    )


class BuildingUpdate(BaseModel):
    """Request body for updating a building. All fields are optional."""

    building_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    building_type: str | None = Field(default=None, pattern=_BUILDING_TYPES)
    construction_status: str | None = Field(default=None, pattern=_CONSTRUCTION_STATUSES)
    footprint_geometry: dict[str, Any] | None = None


class BuildingResponse(BaseModel):
    """Standard JSON response for a building."""

    id: str
    parcel_id: str
    building_identifier: str
    name: str | None = None
    building_type: str
    construction_status: str
    footprint_geometry: dict[str, Any] | None = None
    created_at: str
    updated_at: str

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParcelCreate(BaseModel):
    """Request body for creating a parcel."""

    parcel_identifier: str = Field(min_length=1, max_length=255)
    ulpin: str = Field(min_length=1, max_length=255)
    geometry: dict[str, Any] = Field(
        description="GeoJSON geometry object (MultiPolygon, SRID 4326)"
    )
    area_sqm: float = Field(gt=0)
    status: str = Field(default="draft", pattern=r"^(draft|registered|active|archived)$")
    metadata: dict[str, Any] | None = None


class ParcelUpdate(BaseModel):
    """Request body for updating a parcel. All fields optional."""

    parcel_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    ulpin: str | None = Field(default=None, min_length=1, max_length=255)
    geometry: dict[str, Any] | None = None
    area_sqm: float | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern=r"^(draft|registered|active|archived)$")
    metadata: dict[str, Any] | None = None


class ParcelResponse(BaseModel):
    """Standard JSON response for a parcel (non-geometry fields)."""

    id: str
    parcel_identifier: str
    ulpin: str
    area_sqm: float
    status: str
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class GeoJSONGeometry(BaseModel):
    """GeoJSON geometry structure."""

    type: str
    coordinates: Any


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature wrapping a parcel."""

    type: str = "Feature"
    id: str
    geometry: GeoJSONGeometry
    properties: ParcelResponse


class ULPINResponse(BaseModel):
    """Response for a ULPIN record."""

    id: str
    parcel_id: str
    ulpin_code: str
    issued_date: str
    issuing_authority: str
    checksum: str


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    per_page: int
    total: int
    total_pages: int


class ParcelListResponse(BaseModel):
    """Paginated list of parcels."""

    data: list[GeoJSONFeature]
    meta: PaginationMeta

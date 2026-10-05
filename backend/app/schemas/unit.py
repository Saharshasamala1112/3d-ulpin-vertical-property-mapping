from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

_UNIT_TYPES = r"^(residential|commercial|parking|storage|common_area)$"
_UNIT_STATUSES = r"^(planned|active|sold|leased|archived)$"

_NUMERIC_DIMS = ("x", "y", "z")
VDCStatus = Literal["present", "missing", "stale", "invalid"]

_BoxModel = TypeVar("_BoxModel", bound=BaseModel)


def _validate_bounding_box(model: _BoxModel) -> _BoxModel:
    """Require each spatial dimension to have strictly positive size."""
    for dim in _NUMERIC_DIMS:
        lo = getattr(model, f"{dim}_min")
        hi = getattr(model, f"{dim}_max")
        if lo is not None and hi is not None and lo >= hi:
            raise ValueError(f"{dim}_min must be less than {dim}_max")
    return model


class UnitCreate(BaseModel):
    """Request body for creating a unit within a floor."""

    unit_identifier: str = Field(min_length=1, max_length=255)
    unit_type: str = Field(
        pattern=_UNIT_TYPES,
        description="Type of the unit (residential, commercial, parking, storage, common_area)",
    )
    area_sqm: float = Field(gt=0, description="Floor area of the unit in square meters")
    x_min: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box min X (meters)"
    )
    x_max: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box max X (meters)"
    )
    y_min: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box min Y (meters)"
    )
    y_max: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box max Y (meters)"
    )
    z_min: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box min Z (meters)"
    )
    z_max: Decimal = Field(
        max_digits=18, decimal_places=6, description="Unit bounding box max Z (meters)"
    )
    status: str = Field(
        default="planned",
        pattern=_UNIT_STATUSES,
        description="Status of the unit (planned, active, sold, leased, archived)",
    )
    vdc_code: str | None = Field(
        default=None,
        max_length=255,
        deprecated=True,
        description=(
            "Deprecated compatibility input; ignored. VDC codes are derived from the unit's "
            "parcel, building, floor, and identifier."
        ),
    )

    @model_validator(mode="after")
    def _check_bounding_box(self) -> UnitCreate:
        return _validate_bounding_box(self)


class UnitUpdate(BaseModel):
    """Request body for updating a unit. All fields are optional."""

    floor_id: UUID | None = Field(default=None, description="Move the unit to another floor")
    unit_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    unit_type: str | None = Field(default=None, pattern=_UNIT_TYPES)
    area_sqm: float | None = Field(default=None, gt=0)
    x_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    x_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    y_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    y_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    z_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    z_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    status: str | None = Field(default=None, pattern=_UNIT_STATUSES)
    vdc_code: str | None = Field(
        default=None,
        max_length=255,
        deprecated=True,
        description="Deprecated compatibility input; ignored. Use the unit VDC endpoint.",
    )

    @model_validator(mode="after")
    def _check_bounding_box(self) -> UnitUpdate:
        return _validate_bounding_box(self)


class UnitResponse(BaseModel):
    """Standard JSON response for a unit."""

    id: str
    floor_id: str
    unit_identifier: str
    unit_type: str
    area_sqm: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    status: str
    vdc_code: str | None = None
    vdc_status: VDCStatus = "missing"
    created_at: str
    updated_at: str


class UnitVDCResponse(BaseModel):
    """Response carrying a unit's stored VDC code and its parsed segments.

    The segments are populated only when ``vdc_code`` is present and parses.
    A unit with no VDC code, or with a stored value the parser rejects, returns
    the code with all segments null rather than failing the read.
    """

    unit_id: str
    vdc_code: str | None
    status: VDCStatus = "missing"
    ulpin: str | None = None
    domain: str | None = None
    level: str | None = None
    unit: str | None = None
    checksum: str | None = None

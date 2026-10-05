from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.elevation import ElevationValidationError
from app.schemas.gap import GapResult
from app.schemas.overlap import OverlapResult

DEFAULT_MINIMUM_GAP = Decimal("0.001")
DEFAULT_MAXIMUM_GAP = Decimal("1")


class UnitIdsRequest(BaseModel):
    """Unit IDs to include in a pairwise topology check."""

    unit_ids: list[UUID]


class GapCheckRequest(UnitIdsRequest):
    """Unit IDs and gap distance range for the gap check."""

    minimum_gap: Decimal = Field(default=DEFAULT_MINIMUM_GAP, ge=0, allow_inf_nan=False)
    maximum_gap: Decimal = Field(default=DEFAULT_MAXIMUM_GAP, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _validate_gap_range(self) -> GapCheckRequest:
        if self.maximum_gap <= self.minimum_gap:
            raise ValueError("maximum_gap must be greater than minimum_gap")
        return self


class GeometryValidationError(BaseModel):
    """A geometry validation issue associated with its unit."""

    unit_id: UUID
    code: str
    message: str
    field: str


class ValidationSummary(BaseModel):
    """Overall outcome and per-check issue counts."""

    status: Literal["passed", "failed"]
    valid: bool
    geometry_error_count: int = Field(ge=0)
    overlap_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    elevation_error_count: int = Field(ge=0)


class TopologyValidationReport(BaseModel):
    """Combined read-only topology validation response."""

    summary: ValidationSummary
    geometry_errors: list[GeometryValidationError] = Field(default_factory=list)
    overlap_results: list[OverlapResult] = Field(default_factory=list)
    gap_results: list[GapResult] = Field(default_factory=list)
    elevation_errors: list[ElevationValidationError] = Field(default_factory=list)


def build_topology_report(
    *,
    geometry_errors: list[GeometryValidationError] | None = None,
    overlap_results: list[OverlapResult] | None = None,
    gap_results: list[GapResult] | None = None,
    elevation_errors: list[ElevationValidationError] | None = None,
) -> TopologyValidationReport:
    """Create a report and derive its pass/fail summary from all result groups."""
    geometry_errors = geometry_errors or []
    overlap_results = overlap_results or []
    gap_results = gap_results or []
    elevation_errors = elevation_errors or []
    valid = not (geometry_errors or overlap_results or gap_results or elevation_errors)
    return TopologyValidationReport(
        summary=ValidationSummary(
            status="passed" if valid else "failed",
            valid=valid,
            geometry_error_count=len(geometry_errors),
            overlap_count=len(overlap_results),
            gap_count=len(gap_results),
            elevation_error_count=len(elevation_errors),
        ),
        geometry_errors=geometry_errors,
        overlap_results=overlap_results,
        gap_results=gap_results,
        elevation_errors=elevation_errors,
    )

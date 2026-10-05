from __future__ import annotations

from pydantic import BaseModel, Field


class ElevationValidationError(BaseModel):
    """A structured elevation consistency violation."""

    code: str
    message: str
    floor_id: str | None = None
    unit_id: str | None = None


class ElevationValidationResult(BaseModel):
    """Validation outcome for building floor and unit elevation consistency."""

    valid: bool
    errors: list[ElevationValidationError] = Field(default_factory=list)

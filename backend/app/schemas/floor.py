from __future__ import annotations

from pydantic import BaseModel, Field

_FLOOR_TYPES = r"^(basement|ground|typical|penthouse|rooftop)$"


class FloorCreate(BaseModel):
    """Request body for creating a floor within a building."""

    floor_number: int = Field(description="Floor number within the building")
    level_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-friendly name/level of the floor",
    )
    floor_type: str = Field(
        pattern=_FLOOR_TYPES,
        description="Type of the floor (basement, ground, typical, penthouse, rooftop)",
    )
    elevation_min: float = Field(description="Minimum floor elevation in meters")
    elevation_max: float = Field(description="Maximum floor elevation in meters")


class FloorUpdate(BaseModel):
    """Request body for updating a floor. All fields are optional."""

    floor_number: int | None = None
    level_name: str | None = Field(default=None, min_length=1, max_length=255)
    floor_type: str | None = Field(default=None, pattern=_FLOOR_TYPES)
    elevation_min: float | None = None
    elevation_max: float | None = None


class FloorResponse(BaseModel):
    """Standard JSON response for a floor."""

    id: str
    building_id: str
    floor_number: int
    level_name: str | None = None
    floor_type: str
    elevation_min: float
    elevation_max: float
    created_at: str
    updated_at: str

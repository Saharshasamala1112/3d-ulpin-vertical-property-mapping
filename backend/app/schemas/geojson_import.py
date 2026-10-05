from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MAX_IMPORT_FEATURES = 500
MAX_IMPORT_BYTES = 10 * 1024 * 1024


class GeoJSONFeatureCollection(BaseModel):
    """A bounded GeoJSON request envelope; individual features validate independently."""

    type: Literal["FeatureCollection"]
    features: list[Any] = Field(min_length=1, max_length=MAX_IMPORT_FEATURES)


class FeatureImportResult(BaseModel):
    """Outcome for one feature in an import batch."""

    index: int = Field(description="One-based position in the uploaded FeatureCollection")
    status: Literal["created", "updated", "skipped", "failed"]
    key: str | None = Field(default=None, description="ULPIN or building identifier")
    record_id: str | None = None
    reason: str | None = None


class GeoJSONImportReport(BaseModel):
    """Batch counts and per-feature outcomes."""

    dry_run: bool
    created: int
    updated: int
    skipped: int
    failed: int
    features: list[FeatureImportResult]

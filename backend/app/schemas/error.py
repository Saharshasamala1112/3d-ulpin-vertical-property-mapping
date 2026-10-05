from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized error body returned by the GEOSIX API."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


ERROR_CODE_NOT_FOUND = "NOT_FOUND"
ERROR_CODE_VALIDATION_ERROR = "VALIDATION_ERROR"
ERROR_CODE_INTERNAL_ERROR = "INTERNAL_ERROR"
ERROR_CODE_CONFLICT = "CONFLICT"

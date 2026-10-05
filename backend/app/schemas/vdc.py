from __future__ import annotations

from pydantic import BaseModel, Field


class VDCParsed(BaseModel):
    """The five canonical segments of a parsed Vertical DNA Code."""

    ulpin: str
    domain: str
    level: str
    unit: str
    checksum: str


class VDCErrorDetail(BaseModel):
    """A single structured VDC validation error tied to a specific segment."""

    segment: str
    code: str
    message: str


class VDCGenerateRequest(BaseModel):
    """Component segments to combine into a canonical VDC.

    The four fields mirror the ``generate_vdc()`` service signature exactly. They
    are deliberately unconstrained: the segment grammar belongs to the VDC
    specification and is enforced by the service, so that this API layer never
    duplicates a ULPIN, DOMAIN, LEVEL or UNIT rule.
    """

    ulpin: str = Field(
        description="10-character parcel identifier: 'GEOSX' followed by five digits",
        examples=["GEOSX00001"],
    )
    domain: str = Field(
        description="Domain code A, B, C or D",
        examples=["A"],
    )
    level: str | int = Field(
        description=(
            "Level as a canonical string ('G', 'F1'..'F999', 'B1'..'B999') or as a signed "
            "integer, where 0 is ground, positive values are floors and negative values "
            "are basements"
        ),
        examples=["G", 12, -3],
    )
    unit: str = Field(
        description=(
            "Unit number or code: 1-6 characters of A-Z and 0-9 whose first character is a "
            "letter or a non-zero digit"
        ),
        examples=["1", "25B", "1234AB"],
    )


class VDCGenerateResponse(BaseModel):
    """A generated canonical VDC string."""

    vdc: str = Field(
        description="Canonical VDC in ULPIN-DOMAIN-LEVEL-UNIT-CHECKSUM form",
        examples=["GEOSX00001-A-G-1-ZY"],
    )


class VDCValidateRequest(BaseModel):
    """A VDC string to validate."""

    vdc: str = Field(
        description="Complete VDC string to validate, including its checksum",
        examples=["GEOSX00001-A-G-1-ZY"],
    )


class VDCValidateResponse(BaseModel):
    """Validation outcome for a VDC string.

    ``valid`` is ``True`` only when the string satisfies both the Feature 15
    segment grammar and the Feature 16 checksum. Any failure is reported as
    ``valid=False`` with per-segment detail in ``errors`` rather than as an HTTP
    error, because a malformed VDC is an expected answer to this endpoint.
    """

    valid: bool = Field(
        description="True only when the VDC is well formed and its checksum is correct"
    )
    errors: list[VDCErrorDetail] = Field(
        default_factory=list,
        description="Per-segment validation errors; empty when valid is True",
    )


class VDCParseRequest(BaseModel):
    """A VDC string to decompose into its segments."""

    vdc: str = Field(
        description="Complete VDC string to parse, including its checksum",
        examples=["GEOSX00001-A-G-1-ZY"],
    )

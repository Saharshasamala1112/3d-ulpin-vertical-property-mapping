from __future__ import annotations

import re

from app.schemas.vdc import VDCErrorDetail, VDCParsed

ULPIN_RE = re.compile(r"^GEOSX[0-9]{5}$")
DOMAIN_RE = re.compile(r"^[A-D]$")
LEVEL_RE = re.compile(r"^(?:G|F[1-9][0-9]{0,2}|B[1-9][0-9]{0,2})$")
UNIT_RE = re.compile(r"^[A-Z1-9][A-Z0-9]{0,5}$")
CHECKSUM_RE = re.compile(r"^[0-9A-Z]{2}$")

LOWERCASE_RE = re.compile(r"[a-z]")
INVALID_CHAR_RE = re.compile(r"[^A-Z0-9]")

_SEGMENT_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "ulpin",
        ULPIN_RE,
        "ULPIN must be GEOSX followed by exactly 5 digits (e.g. GEOSX00001)",
    ),
    ("domain", DOMAIN_RE, "DOMAIN must be one of A, B, C, D"),
    (
        "level",
        LEVEL_RE,
        "LEVEL must be G, F1..F999, or B1..B999 with no leading zeros",
    ),
    (
        "unit",
        UNIT_RE,
        "UNIT must be 1-6 characters (A-Z, 0-9) starting with a letter or a non-zero digit",
    ),
    (
        "checksum",
        CHECKSUM_RE,
        "CHECKSUM must be exactly 2 base-36 characters (0-9, A-Z)",
    ),
)


class VDCValidationError(ValueError):
    """Raised when a VDC is invalid; carries structured per-segment errors."""

    def __init__(self, errors: list[VDCErrorDetail]) -> None:
        self.errors: tuple[VDCErrorDetail, ...] = tuple(errors)
        summary = "; ".join(
            f"{error.segment}: {error.code}: {error.message}" for error in self.errors
        )
        super().__init__(f"invalid VDC: {summary}")

    @property
    def error(self) -> VDCErrorDetail:
        return self.errors[0]


def parse_vdc(vdc: str) -> VDCParsed:
    """Parse a VDC into its five segments, raising on any invalid input."""
    errors = validate_vdc(vdc)
    if errors:
        raise VDCValidationError(errors)
    ulpin, domain, level, unit, checksum = vdc.strip().split("-")
    return VDCParsed(ulpin=ulpin, domain=domain, level=level, unit=unit, checksum=checksum)


def validate_vdc(vdc: str) -> list[VDCErrorDetail]:
    """Validate a VDC and return structured errors; empty list means valid."""
    if not isinstance(vdc, str):
        raise TypeError("vdc must be a string")
    errors: list[VDCErrorDetail] = []
    segments = _extract_segments(vdc, errors)
    if segments is not None:
        _validate_segments(segments, errors)
    return errors


def _validate_segments(segments: list[str], errors: list[VDCErrorDetail]) -> None:
    for (name, regex, guidance), segment in zip(_SEGMENT_RULES, segments):
        if error := _validate_segment(name, segment, regex, guidance):
            errors.append(error)


def _validate_segment(
    name: str, segment: str, regex: re.Pattern[str], guidance: str
) -> VDCErrorDetail | None:
    if match := LOWERCASE_RE.search(segment):
        return VDCErrorDetail(
            segment=name,
            code="lowercase_character",
            message=(
                f"{name.upper()} contains lowercase character {match.group()!r}; "
                "lowercase is invalid and must not be uppercased"
            ),
        )
    if match := INVALID_CHAR_RE.search(segment):
        return VDCErrorDetail(
            segment=name,
            code="invalid_character",
            message=(
                f"{name.upper()} contains invalid character {match.group()!r}; "
                "only uppercase A-Z and 0-9 are allowed"
            ),
        )
    if not regex.fullmatch(segment):
        return VDCErrorDetail(
            segment=name,
            code=f"invalid_{name}",
            message=f"invalid {name.upper()}: {guidance}",
        )
    return None


def _extract_segments(vdc: str, errors: list[VDCErrorDetail]) -> list[str] | None:
    candidate = vdc.strip()
    parts = candidate.split("-")
    if len(parts) != 5:
        errors.append(
            VDCErrorDetail(
                segment="structure",
                code="invalid_segment_count",
                message=(f"expected exactly 5 hyphen-separated segments, found {len(parts)}"),
            )
        )
        return None
    for index, part in enumerate(parts):
        if part == "":
            errors.append(
                VDCErrorDetail(
                    segment="structure",
                    code="empty_segment",
                    message=f"segment {index + 1} is empty; empty segments are not allowed",
                )
            )
    if any(part == "" for part in parts):
        return None
    return parts

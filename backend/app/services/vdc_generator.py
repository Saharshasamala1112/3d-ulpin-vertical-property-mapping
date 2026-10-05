"""Pure VDC generation engine (VDC Specification 1.0).

Builds a complete canonical VDC string from its four component segments:
``ULPIN-DOMAIN-LEVEL-UNIT-CHECKSUM``.

The generator owns no state and performs no I/O: no database, filesystem or
network access, no randomness and no timestamps. The same inputs always produce
the same VDC.

Segment rules are not reimplemented here. The four supplied segments are
validated by the Feature 15 validator, and the CHECKSUM is produced by the
Feature 16 engine, so this module is limited to choosing the canonical LEVEL
representation and assembling the final string.
"""

from __future__ import annotations

from app.schemas.vdc import VDCErrorDetail, VDCParsed
from app.validators.vdc_checksum import compute_checksum, verify_checksum
from app.validators.vdc_parser import LEVEL_RE, VDCValidationError, validate_vdc

LevelInput = str | int

SEPARATOR = "-"
GROUND_LEVEL = "G"
MAX_LEVEL_NUMBER = 999

# A structurally valid Base-36 checksum, used only to hand the four supplied
# segments to the Feature 15 validator before the real checksum exists. It is a
# legal CHECKSUM character pair, so it never masks a segment error, and
# compute_checksum ignores the checksum field, so it cannot influence the result.
_PLACEHOLDER_CHECKSUM = "00"

_LEVEL_GUIDANCE = "LEVEL must be G, F1..F999, or B1..B999 with no leading zeros"


def canonical_level(level: LevelInput) -> str:
    """Return the canonical Feature 14 LEVEL segment for a level input.

    Two input forms are accepted:

    * ``str``: a canonical LEVEL segment, validated and returned unchanged --
      ``G``, ``F1``..``F999`` or ``B1``..``B999``.
    * ``int``: a signed level number, mapped as ``0`` -> ``G``, ``1``..``999``
      -> ``F<n>`` and ``-1``..``-999`` -> ``B<n>``.

    Neither a sign character nor a leading zero is ever emitted. Feature 14
    encodes a basement as ``B`` followed by a plain integer, so ``-3`` becomes
    ``B3``; a raised floor likewise becomes ``F<n>`` rather than a signed or
    zero-padded form.
    """
    if isinstance(level, bool):
        raise _level_error(f"invalid LEVEL: expected str or int, got {level!r}")
    if isinstance(level, int):
        return _level_from_number(level)
    if not isinstance(level, str):
        raise _level_error(f"invalid LEVEL: expected str or int, got {type(level).__name__}")
    if not LEVEL_RE.fullmatch(level):
        raise _level_error(f"invalid LEVEL: {_LEVEL_GUIDANCE}")
    return level


def generate_vdc(ulpin: str, domain: str, level: LevelInput, unit: str) -> str:
    """Generate a complete canonical VDC string from its component segments.

    ``ulpin`` must be ``GEOSX`` followed by exactly five digits, ``domain`` one
    of ``A``-``D``, ``level`` anything :func:`canonical_level` accepts, and
    ``unit`` one to six characters of ``A-Z``/``0-9`` whose first character is a
    letter or a non-zero digit.

    Inputs are passed through verbatim: nothing is uppercased, padded or
    otherwise normalized, so a lowercase or zero-padded segment is rejected
    rather than repaired.

    The returned string is guaranteed to parse with the Feature 15 parser and to
    pass Feature 16 checksum verification, both of which are asserted before the
    value is returned.

    Raises:
        VDCValidationError: if any component is invalid. The error is a
            ``ValueError`` carrying one ``VDCErrorDetail`` per offending
            segment.
    """
    canonical = canonical_level(level)
    _require_text("ulpin", ulpin)
    _require_text("domain", domain)
    _require_text("unit", unit)

    candidate = SEPARATOR.join((ulpin, domain, canonical, unit, _PLACEHOLDER_CHECKSUM))
    if errors := validate_vdc(candidate):
        raise VDCValidationError(errors)

    segments = VDCParsed(
        ulpin=ulpin,
        domain=domain,
        level=canonical,
        unit=unit,
        checksum=_PLACEHOLDER_CHECKSUM,
    )
    checksum = compute_checksum(segments)
    vdc = SEPARATOR.join((ulpin, domain, canonical, unit, checksum))

    if not verify_checksum(vdc):
        raise VDCValidationError(
            [
                VDCErrorDetail(
                    segment="checksum",
                    code="checksum_mismatch",
                    message=f"generated VDC failed checksum verification: {vdc}",
                )
            ]
        )
    return vdc


def _level_from_number(level: int) -> str:
    """Map a signed level number to its canonical LEVEL segment."""
    if level == 0:
        return GROUND_LEVEL
    if not -MAX_LEVEL_NUMBER <= level <= MAX_LEVEL_NUMBER:
        raise _level_error(
            f"invalid LEVEL: level {level} is out of range; expected "
            f"-{MAX_LEVEL_NUMBER}..{MAX_LEVEL_NUMBER} (0 means ground)"
        )
    if level > 0:
        return f"F{level}"
    return f"B{-level}"


def _level_error(message: str) -> VDCValidationError:
    return VDCValidationError(
        [VDCErrorDetail(segment="level", code="invalid_level", message=message)]
    )


def _require_text(segment: str, value: object) -> None:
    if not isinstance(value, str):
        raise _text_error(segment, "invalid_type", f"must be a string, got {type(value).__name__}")
    if value != value.strip():
        raise _text_error(
            segment, "invalid_whitespace", "must not contain leading or trailing whitespace"
        )


def _text_error(segment: str, code: str, message: str) -> VDCValidationError:
    return VDCValidationError(
        [VDCErrorDetail(segment=segment, code=code, message=f"{segment.upper()} {message}")]
    )

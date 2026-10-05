from __future__ import annotations

from app.schemas.vdc import VDCErrorDetail, VDCParsed
from app.validators.vdc_checksum import compute_checksum, verify_checksum
from app.validators.vdc_parser import parse_vdc, validate_vdc

CHECKSUM_MISMATCH_CODE = "checksum_mismatch"


def validate_vdc_code(vdc: str) -> list[VDCErrorDetail]:
    """Validate VDC syntax and checksum using the specification validators."""
    errors = validate_vdc(vdc)
    if errors:
        return errors
    if verify_checksum(vdc):
        return []

    parsed: VDCParsed = parse_vdc(vdc)
    expected = compute_checksum(parsed)
    return [
        VDCErrorDetail(
            segment="checksum",
            code=CHECKSUM_MISMATCH_CODE,
            message=(
                f"CHECKSUM does not match these segments: expected {expected!r} "
                f"but found {parsed.checksum!r}"
            ),
        )
    ]

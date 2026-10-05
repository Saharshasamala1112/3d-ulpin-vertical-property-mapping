from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import require_editor
from app.schemas.error import ERROR_CODE_VALIDATION_ERROR, ErrorResponse
from app.schemas.vdc import (
    VDCErrorDetail,
    VDCGenerateRequest,
    VDCGenerateResponse,
    VDCParsed,
    VDCParseRequest,
    VDCValidateRequest,
    VDCValidateResponse,
)
from app.services.vdc_generator import generate_vdc
from app.services.vdc_validation import validate_vdc_code
from app.validators.vdc_parser import VDCValidationError, parse_vdc

# All VDC endpoints are compute operations (POST): they derive codes rather
# than reading persisted cadastre, so they require the editor role — the same
# tier as other write operations in the permission matrix (docs/authentication.md).
router = APIRouter(dependencies=[Depends(require_editor)])


def _collect_errors(vdc: str) -> list[VDCErrorDetail]:
    """Compatibility wrapper for the shared syntax-and-checksum validator."""
    return validate_vdc_code(vdc)


def _http_validation_error(exc: VDCValidationError) -> HTTPException:
    """Convert a VDCValidationError into the project's standardized 422 body.

    The per-segment details are preserved under ``details.vdc_errors`` so callers
    keep the segment-level information the VDC engines provide.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": {
                "code": ERROR_CODE_VALIDATION_ERROR,
                "message": str(exc),
                "details": {"vdc_errors": [error.model_dump() for error in exc.errors]},
            }
        },
    )


@router.post(
    "/generate",
    response_model=VDCGenerateResponse,
    summary="Generate a VDC",
    description=(
        "Combine four component segments into a complete canonical VDC string. "
        "The level may be given as a canonical string ('G', 'F1'..'F999', 'B1'..'B999') "
        "or as a signed integer, where 0 is ground, positive values are floors and "
        "negative values are basements. No sign character and no zero padding is ever "
        "emitted. Generation is pure and idempotent: the same components always produce "
        "the same VDC."
    ),
    responses={
        200: {"description": "VDC generated successfully"},
        422: {"model": ErrorResponse, "description": "A component segment is invalid"},
    },
)
async def generate(body: VDCGenerateRequest) -> VDCGenerateResponse:
    try:
        vdc = generate_vdc(body.ulpin, body.domain, body.level, body.unit)
    except VDCValidationError as exc:
        raise _http_validation_error(exc) from exc
    return VDCGenerateResponse(vdc=vdc)


@router.post(
    "/validate",
    response_model=VDCValidateResponse,
    summary="Validate a VDC",
    description=(
        "Report whether a VDC string is valid. A VDC is valid only when it satisfies "
        "both the segment grammar and its checksum. An invalid VDC is an expected "
        "answer to this endpoint, so it is reported as a successful response with "
        "'valid': false and per-segment detail in 'errors'."
    ),
    responses={
        200: {"description": "Validation completed; inspect 'valid' and 'errors'"},
        422: {"model": ErrorResponse, "description": "Request body is invalid"},
    },
)
async def validate(body: VDCValidateRequest) -> VDCValidateResponse:
    errors = _collect_errors(body.vdc)
    return VDCValidateResponse(valid=not errors, errors=errors)


@router.post(
    "/parse",
    response_model=VDCParsed,
    summary="Parse a VDC",
    description=(
        "Decompose a complete VDC string into its five canonical segments: ulpin, "
        "domain, level, unit and checksum. Outer whitespace is ignored, per the VDC "
        "specification, but lowercase is rejected rather than folded."
    ),
    responses={
        200: {"description": "VDC parsed successfully"},
        422: {"model": ErrorResponse, "description": "The VDC string is invalid"},
    },
)
async def parse(body: VDCParseRequest) -> VDCParsed:
    try:
        return parse_vdc(body.vdc)
    except VDCValidationError as exc:
        raise _http_validation_error(exc) from exc

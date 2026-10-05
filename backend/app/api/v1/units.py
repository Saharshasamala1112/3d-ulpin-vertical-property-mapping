from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession, require_admin, require_editor, require_reader
from app.schemas.auth import ErrorResponse
from app.schemas.unit import UnitCreate, UnitResponse, UnitUpdate, UnitVDCResponse
from app.services.unit import (
    VDCGenerationUnavailableError,
    create_unit,
    delete_unit,
    generate_unit_vdc,
    get_unit,
    get_unit_vdc,
    list_units,
    update_unit,
)

router = APIRouter(dependencies=[Depends(require_reader)])


@router.post(
    "/floors/{floor_id}/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_editor)],
    summary="Create a unit",
    description="Create a unit within a floor. The parent floor must exist.",
    responses={
        201: {"description": "Unit created successfully"},
        404: {"model": ErrorResponse, "description": "Floor not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create(floor_id: str, body: UnitCreate, db: DatabaseSession):
    try:
        return create_unit(db, floor_id, body)
    except ValueError as e:
        error_msg = str(e).lower()
        if any(
            kw in error_msg
            for kw in ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max", "bounding"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/floors/{floor_id}/units",
    response_model=list[UnitResponse],
    summary="List units of a floor",
    description="List all units belonging to a floor. The parent floor must exist.",
    responses={
        200: {"description": "Units listed successfully"},
        404: {"model": ErrorResponse, "description": "Floor not found"},
    },
)
async def list(floor_id: str, db: DatabaseSession):
    try:
        return list_units(db, floor_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/units/{unit_id}",
    response_model=UnitResponse,
    summary="Get unit by ID",
    description="Retrieve a single unit by its ID.",
    responses={
        200: {"description": "Unit found"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
    },
)
async def get(unit_id: str, db: DatabaseSession):
    try:
        return get_unit(db, unit_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.put(
    "/units/{unit_id}",
    response_model=UnitResponse,
    dependencies=[Depends(require_editor)],
    summary="Update a unit",
    description="Update unit attributes. All body fields are optional.",
    responses={
        200: {"description": "Unit updated"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def update(unit_id: str, body: UnitUpdate, db: DatabaseSession):
    try:
        return update_unit(db, unit_id, body)
    except ValueError as e:
        error_msg = str(e).lower()
        if any(
            kw in error_msg
            for kw in ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max", "bounding"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.delete(
    "/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Delete a unit",
    description="Delete a unit by setting its status to 'archived'.",
    responses={
        204: {"description": "Unit archived"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
    },
)
async def delete(unit_id: str, db: DatabaseSession):
    try:
        delete_unit(db, unit_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/units/{unit_id}/vdc",
    response_model=UnitVDCResponse,
    summary="Get VDC code for a unit",
    description=(
        "Retrieve the unit's existing VDC code together with its parsed ULPIN, domain, "
        "level, unit and checksum segments. Returns null when no VDC code has been assigned. "
        "The status indicates whether the stored value is present, missing, stale, or invalid. "
        "VDC generation is not performed."
    ),
    responses={
        200: {"description": "VDC record found (vdc_code may be null)"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
    },
)
async def get_vdc(unit_id: str, db: DatabaseSession):
    try:
        return get_unit_vdc(db, unit_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.post(
    "/units/{unit_id}/vdc",
    response_model=UnitVDCResponse,
    dependencies=[Depends(require_editor)],
    summary="Generate or refresh a unit VDC",
    description=(
        "Derive the VDC segments from the unit's parcel, building, floor, and identifier, "
        "then persist and return the canonical code. Repeated requests are idempotent."
    ),
    responses={
        200: {"description": "VDC generated and persisted"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
        422: {"model": ErrorResponse, "description": "The unit hierarchy cannot be encoded"},
    },
)
async def generate_vdc_for_unit(unit_id: str, db: DatabaseSession):
    try:
        return generate_unit_vdc(db, unit_id)
    except VDCGenerationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc)}},
        ) from exc

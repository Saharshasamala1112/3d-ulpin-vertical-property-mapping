from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession, require_editor, require_reader
from app.schemas.auth import ErrorResponse
from app.schemas.geometry3d import Geometry3DCreate, Geometry3DResponse
from app.services.geometry3d import get_geometry_by_unit, replace_geometry_for_unit

router = APIRouter(dependencies=[Depends(require_reader)])


@router.get(
    "/units/{unit_id}/geometry",
    response_model=Geometry3DResponse,
    summary="Get a unit's 3D geometry",
    description=(
        "Return the persisted 3D bounding-box geometry and its derived volume, centroid, and "
        "dimensions. Returns 404 when the unit or its geometry does not exist."
    ),
    responses={
        200: {"description": "Geometry found"},
        404: {"model": ErrorResponse, "description": "Unit or geometry not found"},
    },
)
async def get_geometry(unit_id: str, db: DatabaseSession):
    try:
        return get_geometry_by_unit(db, unit_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(error)}},
        ) from error


@router.put(
    "/units/{unit_id}/geometry",
    response_model=Geometry3DResponse,
    dependencies=[Depends(require_editor)],
    summary="Create or replace a unit's 3D geometry",
    description=(
        "Create the unit's bounding-box geometry when absent, or replace the existing geometry. "
        "Repeated requests update the same geometry row. Axis minima must be strictly less than "
        "their maxima; invalid bounds or geometry types return 422, and an unknown unit returns "
        "404."
    ),
    responses={
        200: {"description": "Geometry created or replaced"},
        404: {"model": ErrorResponse, "description": "Unit not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def put_geometry(unit_id: str, body: Geometry3DCreate, db: DatabaseSession):
    try:
        return replace_geometry_for_unit(db, unit_id, body)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(error)}},
        ) from error

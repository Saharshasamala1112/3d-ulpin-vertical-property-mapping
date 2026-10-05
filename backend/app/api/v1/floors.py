from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession, require_admin, require_editor, require_reader
from app.schemas.auth import ErrorResponse
from app.schemas.floor import FloorCreate, FloorResponse, FloorUpdate
from app.services.floor import (
    create_floor,
    delete_floor,
    get_floor,
    list_floors,
    update_floor,
)

router = APIRouter(dependencies=[Depends(require_reader)])


@router.post(
    "/buildings/{building_id}/floors",
    response_model=FloorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_editor)],
    summary="Create a floor",
    description="Create a floor within a building. The parent building must exist.",
    responses={
        201: {"description": "Floor created successfully"},
        404: {"model": ErrorResponse, "description": "Building not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create(building_id: str, body: FloorCreate, db: DatabaseSession):
    try:
        return create_floor(db, building_id, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/buildings/{building_id}/floors",
    response_model=list[FloorResponse],
    summary="List floors of a building",
    description="List all floors belonging to a building. The parent building must exist.",
    responses={
        200: {"description": "Floors listed successfully"},
        404: {"model": ErrorResponse, "description": "Building not found"},
    },
)
async def list(building_id: str, db: DatabaseSession):
    try:
        return list_floors(db, building_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/floors/{floor_id}",
    response_model=FloorResponse,
    summary="Get floor by ID",
    description="Retrieve a single floor by its ID.",
    responses={
        200: {"description": "Floor found"},
        404: {"model": ErrorResponse, "description": "Floor not found"},
    },
)
async def get(floor_id: str, db: DatabaseSession):
    try:
        return get_floor(db, floor_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.put(
    "/floors/{floor_id}",
    response_model=FloorResponse,
    dependencies=[Depends(require_editor)],
    summary="Update a floor",
    description="Update floor attributes. All body fields are optional.",
    responses={
        200: {"description": "Floor updated"},
        404: {"model": ErrorResponse, "description": "Floor not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def update(floor_id: str, body: FloorUpdate, db: DatabaseSession):
    try:
        return update_floor(db, floor_id, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.delete(
    "/floors/{floor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Delete a floor",
    description="Delete a floor and its associated units.",
    responses={
        204: {"description": "Floor deleted"},
        404: {"model": ErrorResponse, "description": "Floor not found"},
    },
)
async def delete(floor_id: str, db: DatabaseSession):
    try:
        delete_floor(db, floor_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.import_request import read_feature_collection
from app.core.dependencies import DatabaseSession, require_admin, require_editor, require_reader
from app.schemas.auth import ErrorResponse
from app.schemas.building import BuildingCreate, BuildingResponse, BuildingUpdate
from app.schemas.geojson_import import MAX_IMPORT_BYTES, MAX_IMPORT_FEATURES, GeoJSONImportReport
from app.services.building import (
    create_building,
    delete_building,
    get_building,
    list_buildings,
    update_building,
)
from app.services.geojson_import import import_buildings

router = APIRouter(dependencies=[Depends(require_reader)])

_IMPORT_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["type", "features"],
                "properties": {
                    "type": {"type": "string", "const": "FeatureCollection"},
                    "features": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_IMPORT_FEATURES,
                        "items": {"type": "object"},
                    },
                },
            }
        },
        "application/geo+json": {
            "schema": {
                "type": "object",
                "required": ["type", "features"],
                "properties": {
                    "type": {"type": "string", "const": "FeatureCollection"},
                    "features": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_IMPORT_FEATURES,
                        "items": {"type": "object"},
                    },
                },
            }
        },
    },
}

_VALIDATION_KEYWORDS = ("footprint", "polygon", "geojson")


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": message}},
    )


def _service_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if any(keyword in lowered for keyword in _VALIDATION_KEYWORDS):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "VALIDATION_ERROR", "message": message}},
        )
    return _not_found(message)


@router.post(
    "/buildings/import",
    response_model=GeoJSONImportReport,
    dependencies=[Depends(require_editor)],
    summary="Import building footprints from GeoJSON",
    description=(
        "Validate and upsert Polygon footprints in a GeoJSON FeatureCollection. Supply the "
        "target `parcel_id` on each feature's properties or once as a query parameter. "
        "Each feature runs in its own database savepoint; failures are reported per feature. "
        "Use `dry_run=true` (the default) to preview without writes. Requests are limited to "
        f"{MAX_IMPORT_FEATURES} features and {MAX_IMPORT_BYTES // (1024 * 1024)} MiB; "
        "processing is synchronous."
    ),
    openapi_extra={"requestBody": _IMPORT_REQUEST_BODY},
    responses={
        200: {"description": "Feature outcomes and created/updated/skipped/failed counts"},
        403: {"model": ErrorResponse, "description": "Editor or administrator role required"},
        413: {"model": ErrorResponse, "description": "Request exceeds the configured size limit"},
        422: {"model": ErrorResponse, "description": "Invalid collection envelope or options"},
    },
)
async def import_building_features(
    request: Request,
    db: DatabaseSession,
    dry_run: bool = Query(default=True, description="Preview only; no database writes"),
    parcel_id: str | None = Query(
        default=None,
        description="Default target parcel UUID when a feature has no parcel_id property",
    ),
) -> GeoJSONImportReport:
    collection = await read_feature_collection(request)
    return import_buildings(db, collection, dry_run=dry_run, parcel_id=parcel_id)


@router.post(
    "/parcels/{parcel_id}/buildings",
    response_model=BuildingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_editor)],
    summary="Create a building",
    description=(
        "Create a building under a parcel. The parent parcel must exist. "
        "An optional GeoJSON Polygon footprint may be provided; deep geometry "
        "validation is out of scope."
    ),
    responses={
        201: {"description": "Building created successfully"},
        404: {"model": ErrorResponse, "description": "Parcel not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create(parcel_id: str, body: BuildingCreate, db: DatabaseSession):
    try:
        return create_building(db, parcel_id, body)
    except ValueError as e:
        raise _service_error(e)


@router.get(
    "/parcels/{parcel_id}/buildings",
    response_model=list[BuildingResponse],
    summary="List buildings of a parcel",
    description="List all buildings belonging to a parcel. The parent parcel must exist.",
    responses={
        200: {"description": "Buildings listed successfully"},
        404: {"model": ErrorResponse, "description": "Parcel not found"},
    },
)
async def list(parcel_id: str, db: DatabaseSession):
    try:
        return list_buildings(db, parcel_id)
    except ValueError as e:
        raise _service_error(e)


@router.get(
    "/buildings/{building_id}",
    response_model=BuildingResponse,
    summary="Get building by ID",
    description="Retrieve a single building by its ID.",
    responses={
        200: {"description": "Building found"},
        404: {"model": ErrorResponse, "description": "Building not found"},
    },
)
async def get(building_id: str, db: DatabaseSession):
    try:
        return get_building(db, building_id)
    except ValueError as e:
        raise _service_error(e)


@router.put(
    "/buildings/{building_id}",
    response_model=BuildingResponse,
    dependencies=[Depends(require_editor)],
    summary="Update a building",
    description="Update building attributes. All body fields are optional.",
    responses={
        200: {"description": "Building updated"},
        404: {"model": ErrorResponse, "description": "Building not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def update(building_id: str, body: BuildingUpdate, db: DatabaseSession):
    try:
        return update_building(db, building_id, body)
    except ValueError as e:
        raise _service_error(e)


@router.delete(
    "/buildings/{building_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Delete a building",
    description=(
        "Delete a building. Associated floors and units are removed via database cascade."
    ),
    responses={
        204: {"description": "Building deleted"},
        404: {"model": ErrorResponse, "description": "Building not found"},
    },
)
async def delete(building_id: str, db: DatabaseSession):
    try:
        delete_building(db, building_id)
    except ValueError as e:
        raise _service_error(e)

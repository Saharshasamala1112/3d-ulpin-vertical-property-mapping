from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.import_request import read_feature_collection
from app.core.dependencies import DatabaseSession, require_admin, require_editor, require_reader
from app.schemas.auth import ErrorResponse
from app.schemas.geojson_import import MAX_IMPORT_BYTES, MAX_IMPORT_FEATURES, GeoJSONImportReport
from app.schemas.parcel import (
    ParcelCreate,
    ParcelListResponse,
    ParcelUpdate,
    ULPINResponse,
)
from app.services.geojson_import import import_parcels
from app.services.parcel import (
    create_parcel,
    delete_parcel,
    get_parcel,
    get_ulpin_for_parcel,
    list_parcels,
    update_parcel,
)

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


@router.post(
    "/import",
    response_model=GeoJSONImportReport,
    dependencies=[Depends(require_editor)],
    summary="Import parcels from GeoJSON",
    description=(
        "Validate and upsert a GeoJSON FeatureCollection by the selected ULPIN property "
        "(default `ulpin`). Supports Polygon and MultiPolygon geometry in SRID 4326. "
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
async def import_parcel_features(
    request: Request,
    db: DatabaseSession,
    dry_run: bool = Query(default=True, description="Preview only; no database writes"),
    ulpin_property: str = Query(
        default="ulpin", description="Feature property used as the parcel upsert key"
    ),
) -> GeoJSONImportReport:
    collection = await read_feature_collection(request)
    try:
        return import_parcels(
            db,
            collection,
            dry_run=dry_run,
            ulpin_property=ulpin_property,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        ) from exc


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_editor)],
    summary="Create a new parcel",
    description="Create a new parcel record with GeoJSON geometry (MultiPolygon, SRID 4326).",
    responses={
        201: {"description": "Parcel created successfully"},
        409: {"model": ErrorResponse, "description": "Duplicate ulpin or parcel_identifier"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create(body: ParcelCreate, db: DatabaseSession):
    try:
        return create_parcel(db, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_PARCEL", "message": str(e)}},
        )


@router.get(
    "",
    response_model=ParcelListResponse,
    summary="List parcels",
    description=(
        "List parcels with pagination. Supports filtering by status "
        "and spatial bounding box queries."
    ),
)
async def list(
    db: DatabaseSession,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by parcel status (draft, registered, active, archived)",
    ),
    min_lon: float | None = Query(default=None, description="Bounding box min longitude"),
    min_lat: float | None = Query(default=None, description="Bounding box min latitude"),
    max_lon: float | None = Query(default=None, description="Bounding box max longitude"),
    max_lat: float | None = Query(default=None, description="Bounding box max latitude"),
):
    return list_parcels(
        db,
        page=page,
        per_page=per_page,
        status=status_filter,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
    )


@router.get(
    "/{parcel_id}",
    summary="Get parcel by ID",
    description="Retrieve a single parcel as a GeoJSON Feature with geometry.",
    responses={
        200: {"description": "Parcel found"},
        404: {"model": ErrorResponse, "description": "Parcel not found"},
    },
)
async def get(parcel_id: str, db: DatabaseSession):
    try:
        return get_parcel(db, parcel_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.put(
    "/{parcel_id}",
    dependencies=[Depends(require_editor)],
    summary="Update a parcel",
    description="Update parcel attributes and/or geometry. All body fields are optional.",
    responses={
        200: {"description": "Parcel updated"},
        404: {"model": ErrorResponse, "description": "Parcel not found"},
        409: {"model": ErrorResponse, "description": "Duplicate ulpin or parcel_identifier"},
    },
)
async def update(parcel_id: str, body: ParcelUpdate, db: DatabaseSession):
    try:
        return update_parcel(db, parcel_id, body)
    except ValueError as e:
        code = "NOT_FOUND" if "not found" in str(e).lower() else "DUPLICATE_PARCEL"
        http_status = status.HTTP_404_NOT_FOUND if code == "NOT_FOUND" else status.HTTP_409_CONFLICT
        raise HTTPException(
            status_code=http_status,
            detail={"error": {"code": code, "message": str(e)}},
        )


@router.delete(
    "/{parcel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Soft-delete a parcel",
    description="Soft-delete a parcel by setting its status to 'archived'.",
    responses={
        204: {"description": "Parcel archived"},
        404: {"model": ErrorResponse, "description": "Parcel not found"},
    },
)
async def delete(parcel_id: str, db: DatabaseSession):
    try:
        delete_parcel(db, parcel_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )


@router.get(
    "/{parcel_id}/ulpin",
    response_model=ULPINResponse,
    summary="Get ULPIN for a parcel",
    description="Retrieve the ULPIN record associated with a parcel.",
    responses={
        200: {"description": "ULPIN found"},
        404: {"model": ErrorResponse, "description": "Parcel or ULPIN not found"},
    },
)
async def get_ulpin(parcel_id: str, db: DatabaseSession):
    try:
        return get_ulpin_for_parcel(db, parcel_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )

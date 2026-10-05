from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession, require_editor
from app.schemas.auth import ErrorResponse
from app.schemas.topology import (
    GapCheckRequest,
    TopologyValidationReport,
    UnitIdsRequest,
)
from app.services.topology import (
    TopologyResourceNotFoundError,
    validate_building_topology,
    validate_unit_gaps,
    validate_unit_overlaps,
    validate_unit_topology,
)

# Topology validation endpoints are POST compute operations; per the permission
# matrix (docs/authentication.md) they require the editor role.
router = APIRouter(dependencies=[Depends(require_editor)])


def _not_found(exc: TopologyResourceNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": str(exc)}},
    )


@router.post(
    "/validate/building/{building_id}",
    response_model=TopologyValidationReport,
    summary="Validate building topology",
    description=(
        "Run geometry, volumetric overlap, spatial gap, and floor-elevation checks for "
        "all units in a building. Invalid or missing geometries are reported and excluded "
        "from pairwise checks."
    ),
    responses={404: {"model": ErrorResponse, "description": "Building not found"}},
)
async def validate_building(building_id: UUID, db: DatabaseSession) -> TopologyValidationReport:
    try:
        return validate_building_topology(db, building_id)
    except TopologyResourceNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/validate/unit/{unit_id}",
    response_model=TopologyValidationReport,
    summary="Validate unit geometry",
    description="Validate the 3D geometry associated with a single unit.",
    responses={404: {"model": ErrorResponse, "description": "Unit not found"}},
)
async def validate_unit(unit_id: UUID, db: DatabaseSession) -> TopologyValidationReport:
    try:
        return validate_unit_topology(db, unit_id)
    except TopologyResourceNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/validate/overlaps",
    response_model=TopologyValidationReport,
    summary="Check unit overlaps",
    description=(
        "Validate geometry and detect AABB overlaps among the supplied unit IDs. "
        "Units without valid AABB geometries are returned in geometry_errors."
    ),
    responses={404: {"model": ErrorResponse, "description": "Unit not found"}},
)
async def validate_overlaps(
    body: UnitIdsRequest,
    db: DatabaseSession,
) -> TopologyValidationReport:
    try:
        return validate_unit_overlaps(db, body)
    except TopologyResourceNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/validate/gaps",
    response_model=TopologyValidationReport,
    summary="Check unit gaps",
    description=(
        "Validate geometry and detect spatial gaps among the supplied unit IDs. "
        "Configure minimum_gap and maximum_gap in the request body."
    ),
    responses={404: {"model": ErrorResponse, "description": "Unit not found"}},
)
async def validate_gaps(
    body: GapCheckRequest,
    db: DatabaseSession,
) -> TopologyValidationReport:
    try:
        return validate_unit_gaps(
            db,
            body,
            minimum_gap=body.minimum_gap,
            maximum_gap=body.maximum_gap,
        )
    except TopologyResourceNotFoundError as exc:
        raise _not_found(exc) from exc

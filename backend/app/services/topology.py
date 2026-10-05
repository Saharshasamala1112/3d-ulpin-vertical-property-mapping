from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.floor import Floor
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.unit import Unit
from app.schemas.topology import (
    GeometryValidationError,
    TopologyValidationReport,
    UnitIdsRequest,
    build_topology_report,
)
from app.validators.elevation_validator import validate_elevation_consistency
from app.validators.gap_detector import DEFAULT_MAX_GAP, DEFAULT_MIN_GAP, detect_gaps
from app.validators.geometry3d_validator import validate_geometry
from app.validators.overlap_detector import detect_overlaps


class TopologyResourceNotFoundError(ValueError):
    """A requested building or unit does not exist."""


def validate_building_topology(
    db: Session,
    building_id: UUID,
    *,
    minimum_gap: Decimal = DEFAULT_MIN_GAP,
    maximum_gap: Decimal = DEFAULT_MAX_GAP,
) -> TopologyValidationReport:
    """Run geometry, overlap, gap, and elevation checks for one building."""
    building = db.get(Building, building_id)
    if building is None:
        raise TopologyResourceNotFoundError("Building not found")

    units = (
        db.execute(
            select(Unit)
            .join(Floor, Unit.floor_id == Floor.id)
            .where(Floor.building_id == building_id)
            .order_by(Unit.id)
        )
        .scalars()
        .all()
    )
    geometries, geometry_errors = _validated_geometries(db, units)
    geometry_ids = [geometry.id for geometry in geometries]
    overlap_results = detect_overlaps(geometry_ids, db=db)
    gap_results = detect_gaps(
        geometry_ids,
        minimum_gap=minimum_gap,
        maximum_gap=maximum_gap,
        db=db,
    )
    elevation = validate_elevation_consistency(db, building_id)

    return build_topology_report(
        geometry_errors=geometry_errors,
        overlap_results=overlap_results,
        gap_results=gap_results,
        elevation_errors=elevation.errors,
    )


def validate_unit_topology(db: Session, unit_id: UUID) -> TopologyValidationReport:
    """Validate the geometry for a single unit."""
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise TopologyResourceNotFoundError("Unit not found")
    _, geometry_errors = _validated_geometries(db, [unit])
    return build_topology_report(geometry_errors=geometry_errors)


def validate_unit_overlaps(
    db: Session,
    request: UnitIdsRequest,
) -> TopologyValidationReport:
    """Validate unit geometry, then detect overlaps for the requested units."""
    units = _load_requested_units(db, request.unit_ids)
    geometries, geometry_errors = _validated_geometries(db, units)
    overlaps = detect_overlaps([geometry.id for geometry in geometries], db=db)
    return build_topology_report(geometry_errors=geometry_errors, overlap_results=overlaps)


def validate_unit_gaps(
    db: Session,
    request: UnitIdsRequest,
    *,
    minimum_gap: Decimal = DEFAULT_MIN_GAP,
    maximum_gap: Decimal = DEFAULT_MAX_GAP,
) -> TopologyValidationReport:
    """Validate unit geometry, then detect gaps for the requested units."""
    units = _load_requested_units(db, request.unit_ids)
    geometries, geometry_errors = _validated_geometries(db, units)
    gaps = detect_gaps(
        [geometry.id for geometry in geometries],
        minimum_gap=minimum_gap,
        maximum_gap=maximum_gap,
        db=db,
    )
    return build_topology_report(geometry_errors=geometry_errors, gap_results=gaps)


def _load_requested_units(db: Session, unit_ids: list[UUID]) -> list[Unit]:
    unique_ids = list(dict.fromkeys(unit_ids))
    if not unique_ids:
        return []
    units = (
        db.execute(select(Unit).where(Unit.id.in_(unique_ids)).order_by(Unit.id)).scalars().all()
    )
    found_ids = {unit.id for unit in units}
    missing_ids = sorted(set(unique_ids) - found_ids, key=str)
    if missing_ids:
        missing = ", ".join(str(unit_id) for unit_id in missing_ids)
        raise TopologyResourceNotFoundError(f"Unit not found for ID(s): {missing}")
    return units


def _validated_geometries(
    db: Session,
    units: list[Unit],
) -> tuple[list[PropertyGeometry], list[GeometryValidationError]]:
    if not units:
        return [], []

    geometries = (
        db.execute(
            select(PropertyGeometry)
            .where(PropertyGeometry.unit_id.in_([unit.id for unit in units]))
            .order_by(PropertyGeometry.unit_id)
        )
        .scalars()
        .all()
    )
    by_unit_id = {geometry.unit_id: geometry for geometry in geometries}
    valid_geometries: list[PropertyGeometry] = []
    errors: list[GeometryValidationError] = []

    for unit in units:
        geometry = by_unit_id.get(unit.id)
        if geometry is None:
            errors.append(
                GeometryValidationError(
                    unit_id=unit.id,
                    code="MISSING_GEOMETRY",
                    message="Unit has no 3D property geometry.",
                    field="geometry",
                )
            )
            continue
        if geometry.geometry_type != GeometryType.AABB:
            errors.append(
                GeometryValidationError(
                    unit_id=unit.id,
                    code="UNSUPPORTED_GEOMETRY_TYPE",
                    message="Topology validation currently supports AABB geometries only.",
                    field="geometry_type",
                )
            )
            continue

        result = validate_geometry(geometry)
        errors.extend(
            GeometryValidationError(
                unit_id=unit.id,
                code=issue.code,
                message=issue.message,
                field=issue.field,
            )
            for issue in result.errors
        )
        if result.valid:
            valid_geometries.append(geometry)

    return valid_geometries, errors

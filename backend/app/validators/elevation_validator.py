from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.floor import Floor
from app.models.geometry3d import PropertyGeometry
from app.models.unit import Unit
from app.schemas.elevation import ElevationValidationError, ElevationValidationResult


def validate_elevation_consistency(
    db: Session,
    building_id: UUID,
) -> ElevationValidationResult:
    """Validate floor and unit elevation consistency for a building."""
    building = db.get(Building, building_id)
    if building is None:
        raise ValueError("Building not found")

    floors = (
        db.execute(
            select(Floor)
            .where(Floor.building_id == building_id)
            .order_by(Floor.floor_number.asc(), Floor.id.asc())
        )
        .scalars()
        .all()
    )
    if not floors:
        return ElevationValidationResult(valid=True, errors=[])

    floor_ids = [floor.id for floor in floors]
    geometry_rows = db.execute(
        select(PropertyGeometry, Unit.floor_id)
        .join(Unit, PropertyGeometry.unit_id == Unit.id)
        .where(Unit.floor_id.in_(floor_ids))
    ).all()
    geometry_by_floor: dict[UUID, list[PropertyGeometry]] = {floor_id: [] for floor_id in floor_ids}
    for geometry, floor_id in geometry_rows:
        geometry_by_floor.setdefault(floor_id, []).append(geometry)

    errors = _compute_elevation_errors(floors, geometry_by_floor)
    ordered_errors = sorted(
        errors,
        key=lambda error: (
            error.floor_id or "",
            error.unit_id or "",
            error.code,
        ),
    )
    return ElevationValidationResult(valid=not ordered_errors, errors=ordered_errors)


def _compute_elevation_errors(
    floors: list[Floor],
    geometry_by_floor: dict[UUID, list[PropertyGeometry]],
) -> list[ElevationValidationError]:
    """Evaluate all elevation rules using already-loaded ORM data."""
    errors: list[ElevationValidationError] = []

    ordered_floors = sorted(floors, key=lambda floor: (floor.floor_number, str(floor.id)))

    for floor in ordered_floors:
        floor_geometries = geometry_by_floor.get(floor.id, [])
        if not floor_geometries:
            continue

        canonical_range = (floor_geometries[0].z_min, floor_geometries[0].z_max)
        for geometry in floor_geometries[1:]:
            if (geometry.z_min, geometry.z_max) != canonical_range:
                errors.append(
                    ElevationValidationError(
                        code="ELEVATION_INCONSISTENT",
                        message=(
                            f"Floor {floor.id} contains units with inconsistent elevation ranges."
                        ),
                        floor_id=str(floor.id),
                        unit_id=str(geometry.unit_id),
                    )
                )
                break

    for previous, current in zip(ordered_floors, ordered_floors[1:]):
        if current.floor_number == previous.floor_number:
            errors.append(
                ElevationValidationError(
                    code="ELEVATION_INCONSISTENT",
                    message=(
                        f"Duplicate floor number {current.floor_number} found within the building."
                    ),
                    floor_id=str(current.id),
                )
            )

        if (
            current.elevation_max < previous.elevation_max
            or current.elevation_min < previous.elevation_min
        ):
            errors.append(
                ElevationValidationError(
                    code="ELEVATION_INCONSISTENT",
                    message=(f"Floor {current.id} is below the preceding floor in the building."),
                    floor_id=str(current.id),
                )
            )

        if (
            previous.elevation_max > current.elevation_min
            and current.elevation_max > previous.elevation_min
        ):
            errors.append(
                ElevationValidationError(
                    code="FLOOR_OVERLAP",
                    message=(f"Floor {previous.id} overlaps floor {current.id} in elevation."),
                    floor_id=str(previous.id),
                )
            )
            errors.append(
                ElevationValidationError(
                    code="FLOOR_OVERLAP",
                    message=(f"Floor {current.id} overlaps floor {previous.id} in elevation."),
                    floor_id=str(current.id),
                )
            )

    all_geometries = [
        geometry for floor_geometries in geometry_by_floor.values() for geometry in floor_geometries
    ]
    spanning_unit_ids: set[UUID] = set()
    for geometry in all_geometries:
        intersecting_floors = []
        for floor in ordered_floors:
            if geometry.z_max > floor.elevation_min and geometry.z_min < floor.elevation_max:
                intersecting_floors.append(floor)
        if len(intersecting_floors) > 1:
            spanning_unit_ids.add(geometry.unit_id)
            first_floor = intersecting_floors[0]
            errors.append(
                ElevationValidationError(
                    code="UNIT_SPANS_FLOORS",
                    message=(
                        f"Unit {geometry.unit_id} intersects multiple floors, "
                        f"including {first_floor.id}."
                    ),
                    floor_id=str(first_floor.id),
                    unit_id=str(geometry.unit_id),
                )
            )

    for floor in ordered_floors:
        for geometry in geometry_by_floor.get(floor.id, []):
            # UNIT_SPANS_FLOORS intentionally suppresses the redundant UNIT_OUTSIDE_FLOOR
            # error for the same unit when it crosses multiple floor boundaries.
            if geometry.unit_id in spanning_unit_ids:
                continue
            if geometry.z_min < floor.elevation_min or geometry.z_max > floor.elevation_max:
                errors.append(
                    ElevationValidationError(
                        code="UNIT_OUTSIDE_FLOOR",
                        message=(
                            f"Unit {geometry.unit_id} falls outside the elevation bounds for floor "
                            f"{floor.id}."
                        ),
                        floor_id=str(floor.id),
                        unit_id=str(geometry.unit_id),
                    )
                )

    return errors

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.gap import GapDirection, GapGeometry, GapResult
from app.validators.geometry3d_validator import validate_geometry

DEFAULT_MIN_GAP = Decimal("0.001")
DEFAULT_MAX_GAP = Decimal("1")
_AXES: tuple[GapDirection, ...] = ("x", "y", "z")


def detect_gaps(
    geometry_ids: list[UUID],
    *,
    minimum_gap: Decimal | int | float = DEFAULT_MIN_GAP,
    maximum_gap: Decimal | int | float = DEFAULT_MAX_GAP,
    db: Session | None = None,
) -> list[GapResult]:
    """Find nearby AABB pairs with detectable gaps along one or more axes.

    Gaps at or below ``minimum_gap`` are treated as contact/numerical noise.
    Candidate pairs are considered adjacent only when every separated-axis gap
    is at most ``maximum_gap``. Pass ``db`` to use a caller-owned session;
    otherwise a short-lived application session is opened.
    """
    min_distance = _coerce_tolerance(minimum_gap, "minimum_gap")
    max_distance = _coerce_tolerance(maximum_gap, "maximum_gap")
    if max_distance <= min_distance:
        raise ValueError("maximum_gap must be greater than minimum_gap")

    unique_ids = list(dict.fromkeys(geometry_ids))
    if not unique_ids:
        return []

    if db is not None:
        geometries = _load_geometries(db, unique_ids)
        return _find_gaps(geometries, min_distance, max_distance)

    with SessionLocal() as session:
        geometries = _load_geometries(session, unique_ids)
        return _find_gaps(geometries, min_distance, max_distance)


def _load_geometries(db: Session, geometry_ids: list[UUID]) -> list[PropertyGeometry]:
    geometries = (
        db.execute(select(PropertyGeometry).where(PropertyGeometry.id.in_(geometry_ids)))
        .scalars()
        .all()
    )
    found_ids = {geometry.id for geometry in geometries}
    missing_ids = sorted(set(geometry_ids) - found_ids, key=str)
    if missing_ids:
        missing = ", ".join(str(geometry_id) for geometry_id in missing_ids)
        raise ValueError(f"Geometry not found for ID(s): {missing}")
    return geometries


def _find_gaps(
    geometries: Sequence[PropertyGeometry],
    minimum_gap: Decimal,
    maximum_gap: Decimal,
) -> list[GapResult]:
    unit_ids = [geometry.unit_id for geometry in geometries]
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError("Multiple geometries found for the same unit")
    for geometry in geometries:
        _ensure_supported_geometry(geometry)

    ordered = sorted(
        geometries,
        key=lambda geometry: (
            geometry.x_min,
            geometry.x_max,
            str(geometry.unit_id),
            str(geometry.id),
        ),
    )
    active: list[PropertyGeometry] = []
    gaps: list[GapResult] = []

    for current in ordered:
        active = [
            candidate for candidate in active if candidate.x_max + maximum_gap >= current.x_min
        ]
        for candidate in active:
            gaps.extend(_pair_gaps(candidate, current, minimum_gap, maximum_gap))
        active.append(current)

    return sorted(
        gaps,
        key=lambda gap: (str(gap.unit_a_id), str(gap.unit_b_id), gap.gap_direction),
    )


def _pair_gaps(
    first: PropertyGeometry,
    second: PropertyGeometry,
    minimum_gap: Decimal,
    maximum_gap: Decimal,
) -> list[GapResult]:
    axis_gaps: dict[GapDirection, Decimal] = {}
    region: dict[str, Decimal] = {}

    for axis in _AXES:
        first_min = getattr(first, f"{axis}_min")
        first_max = getattr(first, f"{axis}_max")
        second_min = getattr(second, f"{axis}_min")
        second_max = getattr(second, f"{axis}_max")

        if first_max < second_min:
            distance = second_min - first_max
            region[f"{axis}_min"] = first_max
            region[f"{axis}_max"] = second_min
            axis_gaps[axis] = distance
        elif second_max < first_min:
            distance = first_min - second_max
            region[f"{axis}_min"] = second_max
            region[f"{axis}_max"] = first_min
            axis_gaps[axis] = distance
        else:
            region[f"{axis}_min"] = max(first_min, second_min)
            region[f"{axis}_max"] = min(first_max, second_max)

    if not axis_gaps or any(distance > maximum_gap for distance in axis_gaps.values()):
        return []

    first_id, second_id = sorted((first.unit_id, second.unit_id), key=str)
    gap_geometry = GapGeometry(**region)
    return [
        GapResult(
            unit_a_id=first_id,
            unit_b_id=second_id,
            gap_distance=distance,
            gap_direction=axis,
            gap_geometry=gap_geometry,
        )
        for axis, distance in axis_gaps.items()
        if minimum_gap < distance <= maximum_gap
    ]


def _ensure_supported_geometry(geometry: PropertyGeometry) -> None:
    if geometry.geometry_type != GeometryType.AABB:
        raise ValueError(
            f"Geometry {geometry.id} has unsupported type {geometry.geometry_type!s}; "
            "only AABB geometries can be checked for gaps."
        )

    validation = validate_geometry(geometry, minimum_dimension=0)
    if not validation.valid:
        issues = "; ".join(
            f"{issue.code} ({issue.field}): {issue.message}" for issue in validation.errors
        )
        raise ValueError(f"Geometry {geometry.id} is invalid: {issues}")


def _coerce_tolerance(value: Decimal | int | float, name: str) -> Decimal:
    try:
        distance = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a finite, non-negative number") from error
    if not distance.is_finite() or distance < 0:
        raise ValueError(f"{name} must be a finite, non-negative number")
    return distance

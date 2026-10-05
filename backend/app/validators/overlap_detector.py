from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.overlap import OverlapGeometry, OverlapResult
from app.validators.geometry3d_validator import validate_geometry


def detect_overlaps(
    geometry_ids: list[UUID],
    *,
    db: Session | None = None,
) -> list[OverlapResult]:
    """Find positive-volume AABB intersections among the requested geometries.

    Pass ``db`` to use an existing session; otherwise a short-lived application
    session is opened. The caller is responsible for supplying geometries from
    the building or floor whose units should be compared.
    """
    unique_ids = list(dict.fromkeys(geometry_ids))
    if not unique_ids:
        return []

    if db is not None:
        geometries = _load_geometries(db, unique_ids)
        return _find_overlaps(geometries)

    with SessionLocal() as session:
        geometries = _load_geometries(session, unique_ids)
        return _find_overlaps(geometries)


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


def _find_overlaps(geometries: Sequence[PropertyGeometry]) -> list[OverlapResult]:
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
    overlaps: list[OverlapResult] = []
    for current in ordered:
        active = [candidate for candidate in active if candidate.x_max > current.x_min]
        for candidate in active:
            if _intersects_on_axis(
                candidate.y_min, candidate.y_max, current.y_min, current.y_max
            ) and (
                _intersects_on_axis(candidate.z_min, candidate.z_max, current.z_min, current.z_max)
            ):
                overlaps.append(_make_overlap(candidate, current))
        active.append(current)

    return sorted(overlaps, key=lambda overlap: (str(overlap.unit_a_id), str(overlap.unit_b_id)))


def _ensure_supported_geometry(geometry: PropertyGeometry) -> None:
    if geometry.geometry_type != GeometryType.AABB:
        raise ValueError(
            f"Geometry {geometry.id} has unsupported type {geometry.geometry_type!s}; "
            "only AABB geometries can be checked for overlap."
        )

    validation = validate_geometry(geometry, minimum_dimension=0)
    if not validation.valid:
        issues = "; ".join(
            f"{issue.code} ({issue.field}): {issue.message}" for issue in validation.errors
        )
        raise ValueError(f"Geometry {geometry.id} is invalid: {issues}")


def _intersects_on_axis(
    first_min: Decimal,
    first_max: Decimal,
    second_min: Decimal,
    second_max: Decimal,
) -> bool:
    return first_max > second_min and second_max > first_min


def _make_overlap(first: PropertyGeometry, second: PropertyGeometry) -> OverlapResult:
    x_min = max(first.x_min, second.x_min)
    x_max = min(first.x_max, second.x_max)
    y_min = max(first.y_min, second.y_min)
    y_max = min(first.y_max, second.y_max)
    z_min = max(first.z_min, second.z_min)
    z_max = min(first.z_max, second.z_max)
    first_id, second_id = sorted((first.unit_id, second.unit_id), key=str)
    return OverlapResult(
        unit_a_id=first_id,
        unit_b_id=second_id,
        overlap_volume=(x_max - x_min) * (y_max - y_min) * (z_max - z_min),
        overlap_geometry=OverlapGeometry(
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            z_min=z_min,
            z_max=z_max,
        ),
    )

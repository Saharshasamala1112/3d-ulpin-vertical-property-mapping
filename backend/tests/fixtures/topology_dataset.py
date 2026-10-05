from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.floor import Floor, FloorType
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.parcel import Parcel, ParcelStatus
from app.models.unit import Unit, UnitStatus, UnitType
from app.schemas.geometry3d import GeometryValidationInput

_NAMESPACE = UUID("461874c6-33eb-4533-a89b-c5cd84993c0c")
_TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)
_PARCEL_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.5, 12.9],
                [77.6, 12.9],
                [77.6, 13.0],
                [77.5, 13.0],
                [77.5, 12.9],
            ]
        ]
    ],
}
_BUILDING_FOOTPRINT = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.51, 12.91],
            [77.59, 12.91],
            [77.59, 12.99],
            [77.51, 12.99],
            [77.51, 12.91],
        ]
    ],
}


@dataclass(frozen=True)
class UnitSpec:
    key: str
    x_min: Decimal
    x_max: Decimal
    y_min: Decimal
    y_max: Decimal
    z_min: Decimal
    z_max: Decimal
    geometry_type: GeometryType | None = GeometryType.AABB


@dataclass(frozen=True)
class FloorSpec:
    key: str
    number: int
    elevation_min: Decimal
    elevation_max: Decimal
    units: tuple[UnitSpec, ...]


@dataclass(frozen=True)
class ScenarioSpec:
    key: str
    description: str
    floors: tuple[FloorSpec, ...]
    geometry_codes: frozenset[str] = frozenset()
    overlap_count: int = 0
    gap_count: int = 0
    elevation_codes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SeededScenario:
    spec: ScenarioSpec
    building_id: UUID
    unit_ids: tuple[UUID, ...]


def _d(value: str) -> Decimal:
    return Decimal(value)


def _unit(
    key: str,
    x_min: str,
    x_max: str,
    *,
    z_min: str = "0",
    z_max: str = "3",
    geometry_type: GeometryType | None = GeometryType.AABB,
) -> UnitSpec:
    return UnitSpec(
        key=key,
        x_min=_d(x_min),
        x_max=_d(x_max),
        y_min=_d("0"),
        y_max=_d("1"),
        z_min=_d(z_min),
        z_max=_d(z_max),
        geometry_type=geometry_type,
    )


SCENARIOS = (
    ScenarioSpec(
        key="valid",
        description="One valid unit with no overlaps, gaps, or elevation errors.",
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (_unit("unit-a", "0", "1"),),
            ),
        ),
    ),
    ScenarioSpec(
        key="overlap",
        description="Two AABBs intersect with a positive shared volume.",
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (_unit("unit-a", "0", "2"), _unit("unit-b", "1", "3")),
            ),
        ),
        overlap_count=1,
    ),
    ScenarioSpec(
        key="gap",
        description="Two valid AABBs have a 0.2-unit gap along the x axis.",
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (_unit("unit-a", "0", "1"), _unit("unit-b", "1.2", "2.2")),
            ),
        ),
        gap_count=1,
    ),
    ScenarioSpec(
        key="elevation",
        description=(
            "Overlapping floors contain a spanning unit, an out-of-range unit, "
            "and inconsistent unit elevations."
        ),
        floors=(
            FloorSpec(
                "lower",
                1,
                _d("0"),
                _d("4"),
                (_unit("unit-lower", "0", "1", z_max="4"),),
            ),
            FloorSpec(
                "upper",
                2,
                _d("3"),
                _d("6"),
                (
                    _unit("unit-spanning", "3", "4", z_min="2", z_max="4"),
                    _unit("unit-outside", "6", "7", z_min="5", z_max="7"),
                ),
            ),
        ),
        elevation_codes=frozenset(
            {
                "ELEVATION_INCONSISTENT",
                "FLOOR_OVERLAP",
                "UNIT_SPANS_FLOORS",
                "UNIT_OUTSIDE_FLOOR",
            }
        ),
    ),
    ScenarioSpec(
        key="invalid-geometry",
        description="A persisted non-AABB geometry is rejected as unsupported.",
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (
                    _unit(
                        "unit-invalid",
                        "0",
                        "1",
                        geometry_type=GeometryType.POLYGON_3D,
                    ),
                ),
            ),
        ),
        geometry_codes=frozenset({"UNSUPPORTED_GEOMETRY_TYPE"}),
    ),
    ScenarioSpec(
        key="missing-geometry",
        description="A unit without a property_geometry row reports MISSING_GEOMETRY.",
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (_unit("unit-missing", "0", "1", geometry_type=None),),
            ),
        ),
        geometry_codes=frozenset({"MISSING_GEOMETRY"}),
    ),
    ScenarioSpec(
        key="mixed",
        description=(
            "One report combines an overlap, a gap, unsupported geometry, "
            "and inconsistent elevations."
        ),
        floors=(
            FloorSpec(
                "ground",
                1,
                _d("0"),
                _d("3"),
                (
                    _unit("unit-a", "0", "2"),
                    _unit("unit-b", "1", "3"),
                    _unit("unit-c", "3.2", "4.2"),
                    _unit(
                        "unit-invalid",
                        "7",
                        "8",
                        z_max="2",
                        geometry_type=GeometryType.POLYGON_3D,
                    ),
                ),
            ),
        ),
        geometry_codes=frozenset({"UNSUPPORTED_GEOMETRY_TYPE"}),
        overlap_count=1,
        gap_count=1,
        elevation_codes=frozenset({"ELEVATION_INCONSISTENT"}),
    ),
)

_VALID_GEOMETRY = {
    "x_min": _d("0"),
    "x_max": _d("1"),
    "y_min": _d("0"),
    "y_max": _d("1"),
    "z_min": _d("0"),
    "z_max": _d("1"),
}

# These cases exercise invalid values that database CHECK constraints correctly
# prevent from being persisted as PropertyGeometry rows.
GEOMETRY_VALIDATION_CASES: tuple[tuple[str, GeometryValidationInput | None, str], ...] = (
    ("missing", None, "MISSING_GEOMETRY"),
    (
        "inverted-dimension",
        GeometryValidationInput(**{**_VALID_GEOMETRY, "x_min": _d("2")}),
        "INVALID_DIMENSIONS",
    ),
    (
        "zero-volume",
        GeometryValidationInput(**{**_VALID_GEOMETRY, "x_max": _d("0")}),
        "ZERO_VOLUME",
    ),
    (
        "dimension-below-threshold",
        GeometryValidationInput(**{**_VALID_GEOMETRY, "x_max": _d("0.0005")}),
        "DIMENSION_BELOW_THRESHOLD",
    ),
)


def stable_id(key: str) -> UUID:
    """Return a reproducible UUID for any named dataset entity."""
    return uuid5(_NAMESPACE, f"geosix-topology-dataset:{key}")


def seed_topology_dataset(db: Session) -> dict[str, SeededScenario]:
    """Idempotently insert all topology scenarios and return their stable IDs."""
    seeded: dict[str, SeededScenario] = {}

    for scenario in SCENARIOS:
        parcel_id = stable_id(f"{scenario.key}:parcel")
        building_id = stable_id(f"{scenario.key}:building")
        parcel_suffix = scenario.key.upper().replace("-", "_")

        db.merge(
            Parcel(
                id=parcel_id,
                parcel_identifier=f"TOPOLOGY-DATASET-{parcel_suffix}",
                ulpin=f"TOPOLOGY-DATASET-ULPIN-{parcel_suffix}",
                geometry=func.ST_GeomFromGeoJSON(json.dumps(_PARCEL_GEOMETRY)),
                area_sqm=1000.0,
                status=ParcelStatus.ACTIVE,
                parcel_metadata={"dataset": "topology-validation", "scenario": scenario.key},
                created_at=_TIMESTAMP,
                updated_at=_TIMESTAMP,
            )
        )
        db.flush()
        db.merge(
            Building(
                id=building_id,
                parcel_id=parcel_id,
                building_identifier=f"TOPOLOGY-DATASET-{parcel_suffix}",
                name=f"Topology dataset: {scenario.key}",
                building_type=BuildingType.RESIDENTIAL,
                construction_status=ConstructionStatus.COMPLETED,
                footprint_geometry=func.ST_GeomFromGeoJSON(json.dumps(_BUILDING_FOOTPRINT)),
                created_at=_TIMESTAMP,
                updated_at=_TIMESTAMP,
            )
        )
        db.flush()

        unit_ids: list[UUID] = []
        for floor_spec in scenario.floors:
            floor_id = stable_id(f"{scenario.key}:floor:{floor_spec.key}")
            db.merge(
                Floor(
                    id=floor_id,
                    building_id=building_id,
                    floor_number=floor_spec.number,
                    level_name=floor_spec.key.title(),
                    floor_type=(FloorType.GROUND if floor_spec.number == 1 else FloorType.TYPICAL),
                    elevation_min=floor_spec.elevation_min,
                    elevation_max=floor_spec.elevation_max,
                    created_at=_TIMESTAMP,
                    updated_at=_TIMESTAMP,
                )
            )
            db.flush()

            for unit_spec in floor_spec.units:
                unit_id = stable_id(f"{scenario.key}:unit:{unit_spec.key}")
                unit_ids.append(unit_id)
                db.merge(
                    Unit(
                        id=unit_id,
                        floor_id=floor_id,
                        unit_identifier=f"TOPOLOGY-{parcel_suffix}-{unit_spec.key.upper()}",
                        unit_type=UnitType.RESIDENTIAL,
                        area_sqm=Decimal("1"),
                        status=UnitStatus.ACTIVE,
                        vdc_code=None,
                        created_at=_TIMESTAMP,
                        updated_at=_TIMESTAMP,
                    )
                )
                if unit_spec.geometry_type is not None:
                    db.merge(
                        PropertyGeometry(
                            id=stable_id(f"{scenario.key}:geometry:{unit_spec.key}"),
                            unit_id=unit_id,
                            x_min=unit_spec.x_min,
                            x_max=unit_spec.x_max,
                            y_min=unit_spec.y_min,
                            y_max=unit_spec.y_max,
                            z_min=unit_spec.z_min,
                            z_max=unit_spec.z_max,
                            geometry_type=unit_spec.geometry_type,
                            created_at=_TIMESTAMP,
                            updated_at=_TIMESTAMP,
                        )
                    )
            db.flush()

        seeded[scenario.key] = SeededScenario(
            spec=scenario,
            building_id=building_id,
            unit_ids=tuple(unit_ids),
        )

    return seeded

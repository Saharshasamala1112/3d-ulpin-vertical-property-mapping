"""Test data factories for integration tests.

Plain factory functions, no third-party factory library. Each factory returns a
persisted ORM instance with a valid parent chain, so tests can either read
attributes directly or drive the HTTP API against real rows.

Two schema realities drive the design:

1. Bounding boxes are stored in ``property_geometry`` rather than on ``Unit``.
   The unit factory accepts bounds as geometry overrides and persists them
   through that relationship.
2. ``parcels`` and ``ulpins`` carry unique constraints on ``parcel_identifier``
   and ``ulpin``, and ``buildings`` / ``floors`` cascade from a parcel. Unique
   suffixes keep repeated calls within one test from colliding.
"""

from __future__ import annotations

import itertools
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.floor import Floor, FloorType
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.ownership import Owner, OwnerKind, OwnershipInterest, OwnershipStatus
from app.models.parcel import ULPIN, Parcel, ParcelStatus
from app.models.unit import Unit, UnitStatus, UnitType
from app.services.vdc_integration import vdc_for_unit

# Valid, closed GeoJSON geometries (EPSG:4326 coordinates) in the same shape the
# API accepts.
PARCEL_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.5000, 12.9000],
                [77.6000, 12.9000],
                [77.6000, 13.0000],
                [77.5000, 13.0000],
                [77.5000, 12.9000],
            ]
        ]
    ],
}

# A valid, closed Polygon strictly inside the parcel above.
BUILDING_FOOTPRINT = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.5100, 12.9100],
            [77.5900, 12.9100],
            [77.5900, 12.9900],
            [77.5100, 12.9900],
            [77.5100, 12.9100],
        ]
    ],
}


def _geojson(geometry: dict[str, Any]) -> Any:
    """Build a PostGIS geometry value the way the application services do.

    The services assign ``func.ST_GeomFromGeoJSON(json.dumps(geometry))`` rather
    than a client-side geometry object, and the factories mirror that exactly.
    This matters: a client-side ``WKTElement`` is *not* a subclass of
    ``geoalchemy2.elements.WKBElement``, so it would linger unflushed in the
    identity map and make the response converters take their unsupported
    ``shapely.shape()`` branch.
    """
    return func.ST_GeomFromGeoJSON(json.dumps(geometry))


_counter = itertools.count(1)


def _suffix() -> str:
    """Return a short, collision-free suffix for unique identifier columns."""
    return f"{next(_counter):04d}{uuid.uuid4().hex[:6]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def reset_factories() -> None:
    """Restart the identifier counter so a full run is reproducible."""
    global _counter
    _counter = itertools.count(1)


def _overrides(values: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = {**values, **overrides}
    return merged


def parcel_factory(db: Session, **overrides: Any) -> Parcel:
    """Create and persist a Parcel."""
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "parcel_identifier": f"PARCEL-{_suffix()}",
            "ulpin": f"GEOSX{next(_counter):05d}",
            "geometry": _geojson(PARCEL_GEOMETRY),
            "area_sqm": 1000.0,
            "status": ParcelStatus.ACTIVE,
            "parcel_metadata": {"source": "factory"},
            "created_at": _now(),
            "updated_at": _now(),
        },
        overrides,
    )
    parcel = Parcel(**values)
    db.add(parcel)
    db.flush()
    return parcel


def building_factory(db: Session, parcel: Parcel | None = None, **overrides: Any) -> Building:
    """Create and persist a Building, creating its parent parcel if needed."""
    if parcel is None:
        parcel = parcel_factory(db)
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "parcel_id": parcel.id,
            "building_identifier": f"BLDG-{_suffix()}",
            "name": "Factory Building",
            "building_type": BuildingType.RESIDENTIAL,
            "construction_status": ConstructionStatus.COMPLETED,
            "footprint_geometry": _geojson(BUILDING_FOOTPRINT),
            "created_at": _now(),
            "updated_at": _now(),
        },
        overrides,
    )
    building = Building(**values)
    db.add(building)
    db.flush()
    return building


def floor_factory(db: Session, building: Building | None = None, **overrides: Any) -> Floor:
    """Create and persist a Floor, creating its parent chain if needed."""
    if building is None:
        building = building_factory(db)
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "building_id": building.id,
            "floor_number": 1,
            "level_name": "Ground",
            "floor_type": FloorType.GROUND,
            "elevation_min": Decimal("0.0"),
            "elevation_max": Decimal("3.0"),
            "created_at": _now(),
            "updated_at": _now(),
        },
        overrides,
    )
    floor = Floor(**values)
    db.add(floor)
    db.flush()
    return floor


def ulpin_factory(db: Session, parcel: Parcel | None = None, **overrides: Any) -> ULPIN:
    """Create and persist the ULPIN record issued for a parcel.

    A ``Parcel`` row carries a plain ``ulpin`` string column, but the
    ``/parcels/{id}/ulpin`` endpoint reads the separate ``ulpins`` table and
    returns 404 when no record exists there.
    """
    if parcel is None:
        parcel = parcel_factory(db)
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "parcel_id": parcel.id,
            "ulpin_code": f"ULPIN-CODE-{_suffix()}",
            "issued_date": _now(),
            "issuing_authority": "Test Authority",
            "checksum": uuid.uuid4().hex + uuid.uuid4().hex,
        },
        overrides,
    )
    ulpin = ULPIN(**values)
    db.add(ulpin)
    db.flush()
    return ulpin


def unit_factory(
    db: Session,
    floor: Floor | None = None,
    *,
    geometry: bool = True,
    **overrides: Any,
) -> Unit:
    """Create a Unit and its canonical geometry, creating parent rows as needed."""
    if floor is None:
        floor = floor_factory(db)
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "floor_id": floor.id,
            "unit_identifier": f"U{next(_counter):05d}",
            "unit_type": UnitType.RESIDENTIAL,
            "area_sqm": Decimal("75.0"),
            "x_min": Decimal("0.0"),
            "x_max": Decimal("5.0"),
            "y_min": Decimal("0.0"),
            "y_max": Decimal("5.0"),
            "z_min": Decimal("0.0"),
            "z_max": Decimal("3.0"),
            "status": UnitStatus.ACTIVE,
            "vdc_code": None,
            "created_at": _now(),
            "updated_at": _now(),
        },
        overrides,
    )
    bounds = {
        field: values.pop(field) for field in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    }
    unit = Unit(**values)
    if "vdc_code" not in overrides:
        unit.vdc_code = vdc_for_unit(db, unit, floor=floor)
    db.add(unit)
    db.flush()
    if geometry:
        property_geometry_factory(
            db,
            unit,
            **bounds,
        )
    return unit


def property_geometry_factory(db: Session, unit: Unit, **overrides: Any) -> PropertyGeometry:
    """Create and persist a PropertyGeometry for ``unit``.

    Defaults to a valid AABB (each axis strictly ``min < max``) so the
    ``property_geometry`` CHECK constraints hold unless a test deliberately
    overrides one of them.
    """
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "unit_id": unit.id,
            "x_min": Decimal("0.0"),
            "x_max": Decimal("10.0"),
            "y_min": Decimal("0.0"),
            "y_max": Decimal("5.0"),
            "z_min": Decimal("0.0"),
            "z_max": Decimal("3.0"),
            "geometry_type": GeometryType.AABB,
            "created_at": _now(),
            "updated_at": _now(),
        },
        overrides,
    )
    geometry = db.query(PropertyGeometry).filter_by(unit_id=unit.id).one_or_none()
    if geometry is None:
        geometry = PropertyGeometry(**values)
        db.add(geometry)
    else:
        for field, value in values.items():
            if field not in {"id", "unit_id", "created_at"}:
                setattr(geometry, field, value)
        geometry.updated_at = values["updated_at"]
    unit.geometry = geometry
    db.flush()
    return geometry


def owner_factory(db: Session, **overrides: Any) -> Owner:
    """Create and persist an owner record."""
    now = _now()
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "kind": OwnerKind.INDIVIDUAL,
            "name": f"Owner {_suffix()}",
            "identifier": None,
            "contact_metadata": {},
            "created_at": now,
            "updated_at": now,
        },
        overrides,
    )
    owner = Owner(**values)
    db.add(owner)
    db.flush()
    return owner


def ownership_interest_factory(
    db: Session,
    owner: Owner,
    *,
    parcel: Parcel | None = None,
    unit: Unit | None = None,
    **overrides: Any,
) -> OwnershipInterest:
    """Create an effective-dated interest for exactly one persisted subject."""
    if (parcel is None) == (unit is None):
        raise ValueError("Provide exactly one of parcel or unit")
    now = _now()
    values = _overrides(
        {
            "id": uuid.uuid4(),
            "owner_id": owner.id,
            "parcel_id": parcel.id if parcel else None,
            "unit_id": unit.id if unit else None,
            "share_basis_points": 10000,
            "valid_from": now,
            "valid_to": None,
            "status": OwnershipStatus.ACTIVE,
            "created_at": now,
            "updated_at": now,
        },
        overrides,
    )
    interest = OwnershipInterest(**values)
    db.add(interest)
    db.flush()
    return interest

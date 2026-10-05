from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from app.models.building import Building
from app.models.floor import Floor
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.unit import Unit, UnitStatus, UnitType
from app.schemas.unit import UnitCreate, UnitResponse, UnitUpdate, UnitVDCResponse, VDCStatus
from app.services.vdc_integration import vdc_for_unit
from app.services.vdc_validation import validate_vdc_code
from app.validators.vdc_parser import VDCValidationError, parse_vdc

logger = logging.getLogger("geosix.unit")

_FLOOR_NOT_FOUND = "Floor not found"
_UNIT_NOT_FOUND = "Unit not found"

_BOUND_FIELDS = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")


def _validate_bounds(bounds: dict[str, Decimal]) -> None:
    for axis in ("x", "y", "z"):
        minimum = bounds[f"{axis}_min"]
        maximum = bounds[f"{axis}_max"]
        if not minimum.is_finite() or not maximum.is_finite():
            raise ValueError(f"{axis.upper()} coordinates must be finite numbers")
        if minimum >= maximum:
            raise ValueError(f"{axis}_min must be less than {axis}_max")


def _unit_query(db: Session):
    return db.query(Unit).options(
        selectinload(Unit.geometry),
        selectinload(Unit.floor).selectinload(Floor.building).selectinload(Building.parcel),
    )


def _resolve_vdc_code(db: Session, unit: Unit, floor: Floor | None = None) -> str | None:
    """Derive the only VDC value allowed to be persisted for this unit."""
    return vdc_for_unit(db, unit, floor=floor)


def _vdc_status(db: Session, unit: Unit) -> VDCStatus:
    """Classify a stored code against both its validity and current hierarchy."""
    code = unit.vdc_code
    if code is None:
        return "missing"
    if validate_vdc_code(code):
        return "invalid"
    return "present" if vdc_for_unit(db, unit) == code else "stale"


def _unit_to_response(db: Session, unit: Unit) -> UnitResponse:
    """Convert a Unit ORM object to a response schema."""
    geometry = unit.geometry
    if geometry is None:
        raise RuntimeError(f"Unit {unit.id} has no canonical property geometry")
    return UnitResponse(
        id=str(unit.id),
        floor_id=str(unit.floor_id),
        unit_identifier=unit.unit_identifier,
        unit_type=unit.unit_type.value,
        area_sqm=float(unit.area_sqm),
        x_min=float(geometry.x_min),
        x_max=float(geometry.x_max),
        y_min=float(geometry.y_min),
        y_max=float(geometry.y_max),
        z_min=float(geometry.z_min),
        z_max=float(geometry.z_max),
        status=unit.status.value,
        vdc_code=unit.vdc_code,
        vdc_status=_vdc_status(db, unit),
        created_at=unit.created_at.isoformat(),
        updated_at=unit.updated_at.isoformat(),
    )


def create_unit(db: Session, floor_id: str, data: UnitCreate) -> UnitResponse:
    """Create a unit within a floor. Raises ValueError if the floor does not exist."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None:
        raise ValueError(_FLOOR_NOT_FOUND)

    bounds = {field: Decimal(str(getattr(data, field))) for field in _BOUND_FIELDS}
    _validate_bounds(bounds)
    unit = Unit(
        id=uuid.uuid4(),
        floor_id=floor.id,
        unit_identifier=data.unit_identifier,
        unit_type=UnitType(data.unit_type),
        area_sqm=Decimal(str(data.area_sqm)),
        status=UnitStatus(data.status),
        vdc_code=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    unit.floor = floor
    # Generated before add/commit/refresh, reusing the floor already loaded
    # above, so the code and the row are written in the same transaction.
    if data.vdc_code is not None:
        logger.info(
            "Ignoring caller-supplied VDC for unit %s; codes are hierarchy-derived", unit.id
        )
    unit.vdc_code = _resolve_vdc_code(db, unit, floor=floor)
    unit.geometry = PropertyGeometry(
        id=uuid.uuid4(),
        **bounds,
        geometry_type=GeometryType.AABB,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    logger.info("Unit created: %s (vdc_code=%s)", unit.id, unit.vdc_code)
    return _unit_to_response(db, unit)


def get_unit(db: Session, unit_id: str) -> UnitResponse:
    """Get a unit by ID. Raises ValueError if not found."""
    unit = _unit_query(db).filter(Unit.id == unit_id).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)
    return _unit_to_response(db, unit)


def list_units(db: Session, floor_id: str) -> list[UnitResponse]:
    """List units belonging to a floor. Raises ValueError if the floor does not exist."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None:
        raise ValueError(_FLOOR_NOT_FOUND)

    units = _unit_query(db).filter(Unit.floor_id == floor_id).order_by(Unit.created_at.desc()).all()
    return [_unit_to_response(db, unit) for unit in units]


def update_unit(db: Session, unit_id: str, data: UnitUpdate) -> UnitResponse:
    """Update a unit. Raises ValueError if not found."""
    unit = db.query(Unit).filter(Unit.id == unit_id).with_for_update(of=Unit).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True)
    normalized_updates = {}
    target_floor = None
    supplied_vdc_code = update_data.pop("vdc_code", None)
    if supplied_vdc_code is not None:
        logger.info(
            "Ignoring caller-supplied VDC for unit %s; codes are hierarchy-derived", unit.id
        )

    if update_data.get("floor_id") is not None:
        target_floor = db.query(Floor).filter(Floor.id == update_data.pop("floor_id")).first()
        if target_floor is None:
            raise ValueError(_FLOOR_NOT_FOUND)
        normalized_updates["floor_id"] = target_floor.id
    else:
        update_data.pop("floor_id", None)

    if "unit_type" in update_data and update_data["unit_type"] is not None:
        normalized_updates["unit_type"] = UnitType(update_data.pop("unit_type"))
    if "status" in update_data and update_data["status"] is not None:
        normalized_updates["status"] = UnitStatus(update_data.pop("status"))
    if "area_sqm" in update_data and update_data["area_sqm"] is not None:
        normalized_updates["area_sqm"] = Decimal(str(update_data.pop("area_sqm")))
    for field in _BOUND_FIELDS:
        if field in update_data and update_data[field] is not None:
            normalized_updates[field] = Decimal(str(update_data.pop(field)))

    geometry_updates = {
        field: normalized_updates[field] for field in _BOUND_FIELDS if field in normalized_updates
    }
    if geometry_updates and unit.geometry is None:
        raise RuntimeError(f"Unit {unit.id} has no canonical property geometry")
    if geometry_updates:
        resulting_bbox = {
            field: geometry_updates.get(field, Decimal(str(getattr(unit.geometry, field))))
            for field in _BOUND_FIELDS
        }
        _validate_bounds(resulting_bbox)

    normalized_updates.update(
        {field: value for field, value in update_data.items() if value is not None}
    )
    for field, value in normalized_updates.items():
        if field in geometry_updates:
            setattr(unit.geometry, field, value)
        elif field == "floor_id":
            unit.floor = target_floor
        else:
            setattr(unit, field, value)

    now = datetime.now(timezone.utc)
    unit.updated_at = now
    if geometry_updates:
        unit.geometry.updated_at = now

    if {"floor_id", "unit_identifier"} & normalized_updates.keys():
        unit.vdc_code = _resolve_vdc_code(db, unit, floor=target_floor)

    db.commit()
    db.refresh(unit)
    logger.info("Unit updated: %s", unit.id)
    return _unit_to_response(db, unit)


def delete_unit(db: Session, unit_id: str) -> None:
    """Soft-delete a unit by setting its status to archived. Raises ValueError if not found."""
    unit = _unit_query(db).filter(Unit.id == unit_id).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)
    unit.status = UnitStatus.ARCHIVED
    unit.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Unit soft-deleted (archived): %s", unit.id)


def get_unit_vdc(db: Session, unit_id: str) -> UnitVDCResponse:
    """Get the stored VDC code for a unit plus its parsed segments.

    Read-only: a VDC is never generated or repaired here, so a unit without a
    usable code still answers 200. Segments come from the Feature 15 parser
    when the stored code is valid; a stored value the parser rejects is
    returned as-is with null segments, so historical or hand-written rows stay
    readable instead of turning into a server error.

    Raises ValueError if the unit does not exist.
    """
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)

    code = unit.vdc_code
    code_status = _vdc_status(db, unit)
    if code is None:
        return UnitVDCResponse(unit_id=str(unit.id), vdc_code=None, status=code_status)

    try:
        parsed = parse_vdc(code)
    except VDCValidationError as exc:
        logger.warning("Unit %s stores an unparseable VDC %r: %s", unit.id, code, exc)
        return UnitVDCResponse(unit_id=str(unit.id), vdc_code=code, status=code_status)

    return UnitVDCResponse(
        unit_id=str(unit.id),
        vdc_code=code,
        status=code_status,
        ulpin=parsed.ulpin,
        domain=parsed.domain,
        level=parsed.level,
        unit=parsed.unit,
        checksum=parsed.checksum,
    )


def generate_unit_vdc(db: Session, unit_id: str) -> UnitVDCResponse:
    """Derive and persist a unit VDC while holding a row lock through commit."""
    unit = db.query(Unit).filter(Unit.id == unit_id).with_for_update(of=Unit).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)

    generated = vdc_for_unit(db, unit)
    if generated is None:
        raise VDCGenerationUnavailableError("Unit hierarchy does not produce a valid VDC")

    if unit.vdc_code != generated:
        unit.vdc_code = generated
        unit.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(unit)
    return get_unit_vdc(db, str(unit.id))


class VDCGenerationUnavailableError(ValueError):
    """The persisted unit hierarchy cannot be represented by a canonical VDC."""


def audit_invalid_vdc_codes(db: Session) -> list[tuple[str, str, list[str]]]:
    """Return stored VDCs that fail the same syntax/checksum validation as the API."""
    invalid = []
    for unit_id, code in db.query(Unit.id, Unit.vdc_code).filter(Unit.vdc_code.isnot(None)):
        errors = validate_vdc_code(code)
        if errors:
            invalid.append((str(unit_id), code, [error.message for error in errors]))
    return invalid

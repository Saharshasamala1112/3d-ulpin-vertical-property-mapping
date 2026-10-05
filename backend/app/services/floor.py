from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.floor import Floor, FloorType
from app.schemas.floor import FloorCreate, FloorResponse, FloorUpdate

logger = logging.getLogger("geosix.floor")

_BUILDING_NOT_FOUND = "Building not found"
_FLOOR_NOT_FOUND = "Floor not found"


def _floor_to_response(floor: Floor) -> FloorResponse:
    """Convert a Floor ORM object to a response schema."""
    return FloorResponse(
        id=str(floor.id),
        building_id=str(floor.building_id),
        floor_number=floor.floor_number,
        level_name=floor.level_name,
        floor_type=floor.floor_type.value,
        elevation_min=float(floor.elevation_min),
        elevation_max=float(floor.elevation_max),
        created_at=floor.created_at.isoformat(),
        updated_at=floor.updated_at.isoformat(),
    )


def create_floor(db: Session, building_id: str, data: FloorCreate) -> FloorResponse:
    """Create a floor within a building. Raises ValueError if the building does not exist."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(_BUILDING_NOT_FOUND)

    floor = Floor(
        id=uuid.uuid4(),
        building_id=building.id,
        floor_number=data.floor_number,
        level_name=data.level_name,
        floor_type=FloorType(data.floor_type),
        elevation_min=Decimal(str(data.elevation_min)),
        elevation_max=Decimal(str(data.elevation_max)),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(floor)
    db.commit()
    db.refresh(floor)
    logger.info("Floor created: %s", floor.id)
    return _floor_to_response(floor)


def get_floor(db: Session, floor_id: str) -> FloorResponse:
    """Get a floor by ID. Raises ValueError if not found."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None:
        raise ValueError(_FLOOR_NOT_FOUND)
    return _floor_to_response(floor)


def list_floors(db: Session, building_id: str) -> list[FloorResponse]:
    """List floors belonging to a building. Raises ValueError if the building does not exist."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(_BUILDING_NOT_FOUND)

    floors = (
        db.query(Floor)
        .filter(Floor.building_id == building_id)
        .order_by(Floor.floor_number.asc())
        .all()
    )
    return [_floor_to_response(floor) for floor in floors]


def update_floor(db: Session, floor_id: str, data: FloorUpdate) -> FloorResponse:
    """Update a floor. Raises ValueError if not found."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None:
        raise ValueError(_FLOOR_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True)

    if "floor_type" in update_data and update_data["floor_type"] is not None:
        floor.floor_type = FloorType(update_data["floor_type"])
        del update_data["floor_type"]
    if "elevation_min" in update_data and update_data["elevation_min"] is not None:
        floor.elevation_min = Decimal(str(update_data["elevation_min"]))
        del update_data["elevation_min"]
    if "elevation_max" in update_data and update_data["elevation_max"] is not None:
        floor.elevation_max = Decimal(str(update_data["elevation_max"]))
        del update_data["elevation_max"]

    for field, value in update_data.items():
        if value is not None:
            setattr(floor, field, value)

    floor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(floor)
    logger.info("Floor updated: %s", floor.id)
    return _floor_to_response(floor)


def delete_floor(db: Session, floor_id: str) -> None:
    """Delete a floor. Raises ValueError if not found."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None:
        raise ValueError(_FLOOR_NOT_FOUND)
    db.delete(floor)
    db.commit()
    logger.info("Floor deleted: %s", floor_id)

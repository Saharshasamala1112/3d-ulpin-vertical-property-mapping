from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.parcel import Parcel
from app.schemas.building import BuildingCreate, BuildingResponse, BuildingUpdate

logger = logging.getLogger("geosix.building")

_PARCEL_NOT_FOUND = "Parcel not found"
_BUILDING_NOT_FOUND = "Building not found"


def _footprint_to_geojson(building: Building) -> dict | None:
    """Convert a footprint geometry column to a GeoJSON geometry dict."""
    element = building.footprint_geometry
    if element is None:
        return None

    from geoalchemy2 import WKBElement
    from shapely import wkb
    from shapely.geometry import shape

    if isinstance(element, WKBElement):
        geom = wkb.loads(bytes(element.data))
    else:
        geom = shape(element)
    return {
        "type": geom.geom_type,
        "coordinates": json.loads(json.dumps(geom.__geo_interface__["coordinates"])),
    }


def set_building_footprint(building: Building, geometry: dict) -> None:
    """Set footprint geometry using PostGIS ST_GeomFromGeoJSON (no deep validation)."""
    geom_type = geometry.get("type")
    if geom_type is not None and geom_type != "Polygon":
        raise ValueError("footprint_geometry must be a GeoJSON Polygon")
    building.footprint_geometry = func.ST_GeomFromGeoJSON(json.dumps(geometry))


def _building_to_response(building: Building) -> BuildingResponse:
    """Convert a Building ORM object to a response schema."""
    return BuildingResponse(
        id=str(building.id),
        parcel_id=str(building.parcel_id),
        building_identifier=building.building_identifier,
        name=building.name,
        building_type=building.building_type.value,
        construction_status=building.construction_status.value,
        footprint_geometry=_footprint_to_geojson(building),
        created_at=building.created_at.isoformat(),
        updated_at=building.updated_at.isoformat(),
    )


def create_building(db: Session, parcel_id: str, data: BuildingCreate) -> BuildingResponse:
    """Create a building under a parcel. Raises ValueError if the parcel does not exist."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)

    building = Building(
        id=uuid.uuid4(),
        parcel_id=parcel.id,
        building_identifier=data.building_identifier,
        name=data.name,
        building_type=BuildingType(data.building_type),
        construction_status=ConstructionStatus(data.construction_status),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    if data.footprint_geometry is not None:
        set_building_footprint(building, data.footprint_geometry)
    db.add(building)
    db.commit()
    db.refresh(building)
    logger.info("Building created: %s", building.id)
    return _building_to_response(building)


def get_building(db: Session, building_id: str) -> BuildingResponse:
    """Get a building by ID. Raises ValueError if not found."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(_BUILDING_NOT_FOUND)
    return _building_to_response(building)


def list_buildings(db: Session, parcel_id: str) -> list[BuildingResponse]:
    """List buildings for a parcel. Raises ValueError if the parcel does not exist."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)

    buildings = (
        db.query(Building)
        .filter(Building.parcel_id == parcel_id)
        .order_by(Building.building_identifier.asc())
        .all()
    )
    return [_building_to_response(building) for building in buildings]


def update_building(db: Session, building_id: str, data: BuildingUpdate) -> BuildingResponse:
    """Update a building. Raises ValueError if not found."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(_BUILDING_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True)

    if "footprint_geometry" in update_data:
        footprint = update_data.pop("footprint_geometry")
        if footprint is not None:
            set_building_footprint(building, footprint)

    if "building_type" in update_data and update_data["building_type"] is not None:
        building.building_type = BuildingType(update_data.pop("building_type"))
    if "construction_status" in update_data and update_data["construction_status"] is not None:
        building.construction_status = ConstructionStatus(update_data.pop("construction_status"))

    for field, value in update_data.items():
        if value is not None:
            setattr(building, field, value)

    building.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(building)
    logger.info("Building updated: %s", building.id)
    return _building_to_response(building)


def delete_building(db: Session, building_id: str) -> None:
    """Delete a building. Floors and units cascade via database foreign keys."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(_BUILDING_NOT_FOUND)
    db.delete(building)
    db.commit()
    logger.info("Building deleted: %s", building_id)

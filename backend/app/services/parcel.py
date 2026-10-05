from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone

from shapely import wkb
from shapely.geometry import shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.parcel import ULPIN, Parcel, ParcelStatus
from app.schemas.parcel import (
    GeoJSONFeature,
    GeoJSONGeometry,
    PaginationMeta,
    ParcelCreate,
    ParcelListResponse,
    ParcelResponse,
    ParcelUpdate,
    ULPINResponse,
)

logger = logging.getLogger("geosix.parcel")

_PARCEL_NOT_FOUND = "Parcel not found"


def _geometry_to_geojson(parcel: Parcel) -> GeoJSONGeometry:
    """Convert a GeoAlchemy2 geometry column to GeoJSON geometry dict."""
    from geoalchemy2 import WKBElement

    element = parcel.geometry
    if isinstance(element, WKBElement):
        geom = wkb.loads(bytes(element.data))
    else:
        geom = shape(element)
    return GeoJSONGeometry(
        type=geom.geom_type,
        coordinates=json.loads(json.dumps(geom.__geo_interface__["coordinates"])),
    )


def _parcel_to_feature(parcel: Parcel) -> GeoJSONFeature:
    """Convert a Parcel ORM object to a GeoJSON Feature."""
    return GeoJSONFeature(
        id=str(parcel.id),
        geometry=_geometry_to_geojson(parcel),
        properties=ParcelResponse(
            id=str(parcel.id),
            parcel_identifier=parcel.parcel_identifier,
            ulpin=parcel.ulpin,
            area_sqm=parcel.area_sqm,
            status=parcel.status.value,
            metadata=parcel.parcel_metadata,
            created_at=parcel.created_at.isoformat(),
            updated_at=parcel.updated_at.isoformat(),
        ),
    )


def _ulpin_to_response(ulpin: ULPIN) -> ULPINResponse:
    """Convert a ULPIN ORM object to a response schema."""
    return ULPINResponse(
        id=str(ulpin.id),
        parcel_id=str(ulpin.parcel_id),
        ulpin_code=ulpin.ulpin_code,
        issued_date=ulpin.issued_date.isoformat(),
        issuing_authority=ulpin.issuing_authority,
        checksum=ulpin.checksum,
    )


def set_parcel_geometry(db: Session, parcel: Parcel, geometry: dict) -> None:
    """Set geometry on a parcel using PostGIS ST_GeomFromGeoJSON."""
    parcel.geometry = func.ST_GeomFromGeoJSON(json.dumps(geometry))


def create_parcel(db: Session, data: ParcelCreate) -> GeoJSONFeature:
    """Create a new parcel. Raises ValueError on duplicate ulpin or identifier."""
    existing = (
        db.query(Parcel)
        .filter((Parcel.ulpin == data.ulpin) | (Parcel.parcel_identifier == data.parcel_identifier))
        .first()
    )
    if existing:
        raise ValueError("Parcel with this ulpin or parcel_identifier already exists")

    parcel = Parcel(
        id=uuid.uuid4(),
        parcel_identifier=data.parcel_identifier,
        ulpin=data.ulpin,
        area_sqm=data.area_sqm,
        status=ParcelStatus(data.status),
        parcel_metadata=data.metadata or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    set_parcel_geometry(db, parcel, data.geometry)
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    logger.info("Parcel created: %s", parcel.id)
    return _parcel_to_feature(parcel)


def get_parcel(db: Session, parcel_id: str) -> GeoJSONFeature:
    """Get a parcel by ID. Raises ValueError if not found."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)
    return _parcel_to_feature(parcel)


def list_parcels(
    db: Session,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
) -> ParcelListResponse:
    """List parcels with pagination, optional status filter, and bounding box filter."""
    query = db.query(Parcel)

    if status:
        query = query.filter(Parcel.status == ParcelStatus(status))

    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox_wkt = (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
            f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
        )
        bbox_geom = func.ST_GeomFromText(bbox_wkt, 4326)
        query = query.filter(func.ST_Intersects(Parcel.geometry, bbox_geom))

    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    offset = (page - 1) * per_page
    parcels = query.order_by(Parcel.created_at.desc()).offset(offset).limit(per_page).all()

    return ParcelListResponse(
        data=[_parcel_to_feature(p) for p in parcels],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


def update_parcel(db: Session, parcel_id: str, data: ParcelUpdate) -> GeoJSONFeature:
    """Update a parcel. Raises ValueError if not found or duplicate."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True)

    if "geometry" in update_data and update_data["geometry"] is not None:
        set_parcel_geometry(db, parcel, update_data["geometry"])
        del update_data["geometry"]

    if "status" in update_data and update_data["status"] is not None:
        parcel.status = ParcelStatus(update_data["status"])
        del update_data["status"]

    if "metadata" in update_data:
        parcel.parcel_metadata = update_data["metadata"]
        del update_data["metadata"]

    for field, value in update_data.items():
        if value is not None:
            setattr(parcel, field, value)

    # Check uniqueness if ulpin or parcel_identifier changed
    if "ulpin" in update_data or "parcel_identifier" in update_data:
        existing = (
            db.query(Parcel)
            .filter(
                Parcel.id != parcel.id,
                (Parcel.ulpin == parcel.ulpin)
                | (Parcel.parcel_identifier == parcel.parcel_identifier),
            )
            .first()
        )
        if existing:
            raise ValueError("Parcel with this ulpin or parcel_identifier already exists")

    parcel.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(parcel)
    logger.info("Parcel updated: %s", parcel.id)
    return _parcel_to_feature(parcel)


def delete_parcel(db: Session, parcel_id: str) -> None:
    """Soft-delete a parcel by setting status to archived. Raises ValueError if not found."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)
    parcel.status = ParcelStatus.ARCHIVED
    parcel.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Parcel soft-deleted (archived): %s", parcel.id)


def get_ulpin_for_parcel(db: Session, parcel_id: str) -> ULPINResponse:
    """Get the ULPIN record for a parcel. Raises ValueError if parcel or ULPIN not found."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise ValueError(_PARCEL_NOT_FOUND)
    ulpin = db.query(ULPIN).filter(ULPIN.parcel_id == parcel.id).first()
    if ulpin is None:
        raise ValueError("ULPIN not found for this parcel")
    return _ulpin_to_response(ulpin)

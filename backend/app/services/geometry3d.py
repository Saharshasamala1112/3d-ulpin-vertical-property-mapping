from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.geometry3d import PropertyGeometry
from app.models.unit import Unit
from app.schemas.geometry3d import Geometry3DCreate

logger = logging.getLogger("geosix.geometry3d")

_UNIT_NOT_FOUND = "Unit not found"
_GEOMETRY_NOT_FOUND = "Geometry not found"


def get_geometry_by_unit(db: Session, unit_id: str) -> PropertyGeometry:
    """Return a unit's geometry, raising ValueError if either resource is absent."""
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)

    geometry = db.query(PropertyGeometry).filter(PropertyGeometry.unit_id == unit.id).first()
    if geometry is None:
        raise ValueError(_GEOMETRY_NOT_FOUND)
    return geometry


def replace_geometry_for_unit(
    db: Session, unit_id: str, data: Geometry3DCreate
) -> PropertyGeometry:
    """Create or replace the single bounding-box geometry belonging to a unit."""
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if unit is None:
        raise ValueError(_UNIT_NOT_FOUND)

    geometry = db.query(PropertyGeometry).filter(PropertyGeometry.unit_id == unit.id).first()
    now = datetime.now(timezone.utc)
    values = data.model_dump()
    if geometry is None:
        geometry = PropertyGeometry(
            id=uuid.uuid4(),
            unit_id=unit.id,
            created_at=now,
            updated_at=now,
            **values,
        )
        db.add(geometry)
    else:
        for field, value in values.items():
            setattr(geometry, field, value)
        geometry.updated_at = now

    unit.updated_at = now
    db.commit()
    db.refresh(geometry)
    logger.info("Geometry saved for unit: %s", unit.id)
    return geometry

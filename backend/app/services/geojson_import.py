from __future__ import annotations

import json
import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, mapping, shape
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.parcel import Parcel, ParcelStatus
from app.schemas.geojson_import import (
    FeatureImportResult,
    GeoJSONFeatureCollection,
    GeoJSONImportReport,
)
from app.services.building import set_building_footprint
from app.services.parcel import set_parcel_geometry
from app.validators.vdc_parser import ULPIN_RE

logger = logging.getLogger("geosix.geojson_import")

_PROPERTY_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_PARCEL_STATUSES = {item.value for item in ParcelStatus}
_BUILDING_TYPES = {item.value for item in BuildingType}
_CONSTRUCTION_STATUSES = {item.value for item in ConstructionStatus}


class FeatureImportError(ValueError):
    """A validation failure attributable to one input feature."""


def import_parcels(
    db: Session,
    collection: GeoJSONFeatureCollection,
    *,
    dry_run: bool,
    ulpin_property: str = "ulpin",
) -> GeoJSONImportReport:
    """Validate and upsert each parcel inside its own transaction savepoint."""
    if not _PROPERTY_NAME_RE.fullmatch(ulpin_property):
        raise ValueError("ulpin_property must be a simple GeoJSON property name.")

    outcomes: list[FeatureImportResult] = []
    for index, raw_feature in enumerate(collection.features, start=1):
        try:
            values, normalized_geometry = _parcel_values(raw_feature, ulpin_property)
            existing = db.query(Parcel).filter(Parcel.ulpin == values["ulpin"]).first()
            duplicate_query = db.query(Parcel).filter(
                Parcel.parcel_identifier == values["parcel_identifier"]
            )
            if existing is not None:
                duplicate_query = duplicate_query.filter(Parcel.id != existing.id)
            duplicate_identifier = duplicate_query.first()
            if duplicate_identifier is not None:
                raise FeatureImportError(
                    "parcel_identifier is already assigned to a different ULPIN."
                )

            outcome = _parcel_action(db, index, existing, values, normalized_geometry)
            if not dry_run and outcome.status in {"created", "updated"}:
                try:
                    with db.begin_nested():
                        if existing is None:
                            existing = Parcel(
                                id=uuid.uuid4(),
                                parcel_identifier=values["parcel_identifier"],
                                ulpin=values["ulpin"],
                                area_sqm=values["area_sqm"],
                                status=ParcelStatus(values["status"]),
                                parcel_metadata=values["metadata"],
                                created_at=datetime.now(timezone.utc),
                                updated_at=datetime.now(timezone.utc),
                            )
                            db.add(existing)
                        else:
                            existing.parcel_identifier = values["parcel_identifier"]
                            existing.area_sqm = values["area_sqm"]
                            existing.status = ParcelStatus(values["status"])
                            existing.parcel_metadata = values["metadata"]
                            existing.updated_at = datetime.now(timezone.utc)
                        set_parcel_geometry(db, existing, normalized_geometry)
                        db.flush()
                except IntegrityError:
                    outcome.status = "failed"
                    outcome.record_id = None
                    outcome.reason = "Database uniqueness constraint rejected this feature."
                    outcomes.append(outcome)
                    continue
                outcome.record_id = str(existing.id)
            elif existing is not None:
                outcome.record_id = str(existing.id)
            outcomes.append(outcome)
        except FeatureImportError as exc:
            outcomes.append(_failed(index, _feature_key(raw_feature, ulpin_property), str(exc)))
        except (TypeError, ValueError, KeyError, GEOSException, OverflowError) as exc:
            outcomes.append(_failed(index, _feature_key(raw_feature, ulpin_property), str(exc)))
        except SQLAlchemyError:
            logger.exception("Could not import parcel feature %s", index)
            outcomes.append(
                _failed(
                    index,
                    _feature_key(raw_feature, ulpin_property),
                    "Database rejected this feature.",
                )
            )

    if not dry_run:
        _commit_batch(db)
    return _report(dry_run, outcomes)


def import_buildings(
    db: Session,
    collection: GeoJSONFeatureCollection,
    *,
    dry_run: bool,
    parcel_id: str | None = None,
) -> GeoJSONImportReport:
    """Validate and upsert building footprints, continuing after feature errors."""
    outcomes: list[FeatureImportResult] = []
    for index, raw_feature in enumerate(collection.features, start=1):
        key: str | None = None
        try:
            properties = _feature_properties(raw_feature)
            key = _required_text(properties, "building_identifier", alternate="name")
            selected_parcel_id = properties.get("parcel_id", parcel_id)
            if not isinstance(selected_parcel_id, str) or not selected_parcel_id.strip():
                raise FeatureImportError(
                    "Set parcel_id on the feature or as the request-level parcel_id."
                )
            try:
                parsed_parcel_id = uuid.UUID(selected_parcel_id)
            except ValueError as exc:
                raise FeatureImportError("parcel_id must be a valid parcel UUID.") from exc
            parcel = db.get(Parcel, parsed_parcel_id)
            if parcel is None:
                raise FeatureImportError(f"Parcel {parsed_parcel_id} does not exist.")

            geometry = _validated_geometry(_raw_geometry(raw_feature), {"Polygon"})
            building_type = properties.get("building_type", "residential")
            construction_status = properties.get("construction_status", "planned")
            if building_type not in _BUILDING_TYPES:
                raise FeatureImportError(
                    f"building_type must be one of: {', '.join(sorted(_BUILDING_TYPES))}."
                )
            if construction_status not in _CONSTRUCTION_STATUSES:
                raise FeatureImportError(
                    "construction_status must be one of: "
                    f"{', '.join(sorted(_CONSTRUCTION_STATUSES))}."
                )
            name = properties.get("name")
            if name is not None and (
                not isinstance(name, str) or not 1 <= len(name.strip()) <= 255
            ):
                raise FeatureImportError("name must contain 1 to 255 characters.")
            values = {
                "parcel_id": parsed_parcel_id,
                "building_identifier": key,
                "name": name.strip() if isinstance(name, str) else None,
                "building_type": building_type,
                "construction_status": construction_status,
            }
            existing = (
                db.query(Building)
                .filter(
                    Building.parcel_id == parsed_parcel_id,
                    Building.building_identifier == key,
                )
                .first()
            )
            same = existing is not None and _building_matches(db, existing, values, geometry)
            if same:
                outcomes.append(
                    FeatureImportResult(
                        index=index,
                        key=key,
                        record_id=str(existing.id),
                        status="skipped",
                    )
                )
                continue

            action = "updated" if existing is not None else "created"
            outcome = FeatureImportResult(
                index=index,
                key=key,
                record_id=str(existing.id) if existing is not None else None,
                status=action,
            )
            if not dry_run:
                try:
                    with db.begin_nested():
                        if existing is None:
                            existing = Building(
                                id=uuid.uuid4(),
                                parcel_id=parsed_parcel_id,
                                building_identifier=key,
                                name=values["name"],
                                building_type=BuildingType(building_type),
                                construction_status=ConstructionStatus(construction_status),
                                created_at=datetime.now(timezone.utc),
                                updated_at=datetime.now(timezone.utc),
                            )
                            db.add(existing)
                        else:
                            existing.name = values["name"]
                            existing.building_type = BuildingType(building_type)
                            existing.construction_status = ConstructionStatus(construction_status)
                            existing.updated_at = datetime.now(timezone.utc)
                        set_building_footprint(existing, geometry)
                        db.flush()
                except IntegrityError:
                    outcomes.append(
                        _failed(
                            index,
                            key,
                            "Database constraint rejected this building feature.",
                        )
                    )
                    continue
                outcome.record_id = str(existing.id)
            outcomes.append(outcome)
        except FeatureImportError as exc:
            outcomes.append(_failed(index, key, str(exc)))
        except (TypeError, ValueError, KeyError, GEOSException, OverflowError) as exc:
            outcomes.append(
                _failed(
                    index,
                    key or _feature_key(raw_feature, "building_identifier"),
                    str(exc),
                )
            )
        except SQLAlchemyError:
            logger.exception("Could not import building feature %s", index)
            outcomes.append(_failed(index, key, "Database rejected this feature."))

    if not dry_run:
        _commit_batch(db)
    return _report(dry_run, outcomes)


def _parcel_values(raw_feature: Any, ulpin_property: str) -> tuple[dict[str, Any], dict[str, Any]]:
    properties = _feature_properties(raw_feature)
    ulpin = _required_text(properties, ulpin_property)
    if not ULPIN_RE.fullmatch(ulpin):
        raise FeatureImportError("ULPIN must be GEOSX followed by exactly 5 digits.")
    identifier = _required_text(properties, "parcel_identifier", alternate="name")
    area = properties.get("area_sqm")
    if isinstance(area, bool) or not isinstance(area, (int, float)):
        raise FeatureImportError("area_sqm must be a finite number greater than zero.")
    area = float(area)
    if not math.isfinite(area) or area <= 0:
        raise FeatureImportError("area_sqm must be a finite number greater than zero.")
    status = properties.get("status", "draft")
    if status not in _PARCEL_STATUSES:
        raise FeatureImportError(f"status must be one of: {', '.join(sorted(_PARCEL_STATUSES))}.")
    metadata = properties.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise FeatureImportError("metadata must be an object when supplied.")
    geometry = _validated_geometry(
        _raw_geometry(raw_feature),
        {"Polygon", "MultiPolygon"},
        normalize_polygon_to_multipolygon=True,
    )
    return (
        {
            "ulpin": ulpin,
            "parcel_identifier": identifier,
            "area_sqm": area,
            "status": status,
            "metadata": metadata,
        },
        geometry,
    )


def _parcel_action(
    db: Session,
    index: int,
    existing: Parcel | None,
    values: dict[str, Any],
    geometry: dict[str, Any],
) -> FeatureImportResult:
    if existing is None:
        return FeatureImportResult(index=index, key=values["ulpin"], status="created")
    if (
        existing.parcel_identifier == values["parcel_identifier"]
        and existing.area_sqm == values["area_sqm"]
        and existing.status.value == values["status"]
        and existing.parcel_metadata == values["metadata"]
        and _stored_geometry_matches(db, Parcel, existing.id, geometry)
    ):
        return FeatureImportResult(
            index=index, key=values["ulpin"], record_id=str(existing.id), status="skipped"
        )
    return FeatureImportResult(
        index=index, key=values["ulpin"], record_id=str(existing.id), status="updated"
    )


def _building_matches(
    db: Session,
    existing: Building,
    values: dict[str, Any],
    geometry: dict[str, Any],
) -> bool:
    return (
        existing.name == values["name"]
        and existing.building_type.value == values["building_type"]
        and existing.construction_status.value == values["construction_status"]
        and _stored_geometry_matches(db, Building, existing.id, geometry, "footprint_geometry")
    )


def _stored_geometry_matches(
    db: Session,
    model: type[Parcel] | type[Building],
    record_id: uuid.UUID,
    geometry: dict[str, Any],
    column_name: str = "geometry",
) -> bool:
    column = getattr(model, column_name)
    encoded = db.query(func.ST_AsGeoJSON(column)).filter(model.id == record_id).scalar()
    if encoded is None:
        return False
    return shape(json.loads(encoded)).equals(shape(geometry))


def _validated_geometry(
    raw_geometry: Any,
    allowed_types: set[str],
    *,
    normalize_polygon_to_multipolygon: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw_geometry, dict):
        raise FeatureImportError("geometry must be a GeoJSON geometry object.")
    geometry_type = raw_geometry.get("type")
    if geometry_type not in allowed_types:
        allowed = " or ".join(sorted(allowed_types))
        raise FeatureImportError(f"geometry type must be {allowed}.")
    try:
        parsed = shape(raw_geometry)
    except (TypeError, ValueError, KeyError, GEOSException) as exc:
        raise FeatureImportError(f"geometry is malformed: {exc}") from exc
    if parsed.is_empty:
        raise FeatureImportError("geometry must not be empty.")
    if parsed.has_z:
        raise FeatureImportError(
            "geometry must use two-dimensional longitude/latitude coordinates."
        )
    if not parsed.is_valid:
        from shapely.validation import explain_validity

        raise FeatureImportError(f"geometry is invalid: {explain_validity(parsed)}.")
    if any(not math.isfinite(value) for value in parsed.bounds):
        raise FeatureImportError("geometry coordinates must be finite.")
    min_x, min_y, max_x, max_y = parsed.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        raise FeatureImportError("geometry coordinates must be longitude/latitude in SRID 4326.")
    if normalize_polygon_to_multipolygon and parsed.geom_type == "Polygon":
        parsed = MultiPolygon([parsed])
    return mapping(parsed)


def _feature_properties(raw_feature: Any) -> dict[str, Any]:
    if not isinstance(raw_feature, dict) or raw_feature.get("type") != "Feature":
        raise FeatureImportError("Each item must be a GeoJSON Feature.")
    properties = raw_feature.get("properties")
    if not isinstance(properties, dict):
        raise FeatureImportError("Feature properties must be an object.")
    return properties


def _raw_geometry(raw_feature: Any) -> Any:
    if not isinstance(raw_feature, dict):
        raise FeatureImportError("Each item must be a GeoJSON Feature.")
    return raw_feature.get("geometry")


def _required_text(properties: dict[str, Any], key: str, *, alternate: str | None = None) -> str:
    value = properties.get(key)
    if value is None and alternate:
        value = properties.get(alternate)
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 255:
        label = f"{key} (or {alternate})" if alternate else key
        raise FeatureImportError(f"{label} must contain 1 to 255 characters.")
    return value.strip()


def _feature_key(raw_feature: Any, key_name: str) -> str | None:
    if not isinstance(raw_feature, dict):
        return None
    properties = raw_feature.get("properties")
    if not isinstance(properties, dict):
        return None
    value = properties.get(key_name)
    return value if isinstance(value, str) else None


def _failed(index: int, key: str | None, reason: str) -> FeatureImportResult:
    return FeatureImportResult(index=index, key=key, status="failed", reason=reason)


def _report(dry_run: bool, outcomes: list[FeatureImportResult]) -> GeoJSONImportReport:
    counts = Counter(item.status for item in outcomes)
    return GeoJSONImportReport(
        dry_run=dry_run,
        created=counts["created"],
        updated=counts["updated"],
        skipped=counts["skipped"],
        failed=counts["failed"],
        features=outcomes,
    )


def _commit_batch(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("GeoJSON batch transaction failed during commit")
        raise

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.validators.elevation_validator import validate_elevation_consistency
from tests.integration import factories


def test_valid_building_floor_and_unit_chain(db_session: Session):
    building = factories.building_factory(db_session)
    floor = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    factories.unit_factory(
        db_session,
        floor=floor,
        z_min=Decimal("0.0"),
        z_max=Decimal("3.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is True
    assert result.errors == []


def test_overlapping_floors_are_detected(db_session: Session):
    building = factories.building_factory(db_session)
    floor_1 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("4.0"),
    )
    floor_2 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is False
    assert {error.code for error in result.errors} >= {"FLOOR_OVERLAP"}
    assert any(error.floor_id == str(floor_1.id) for error in result.errors)
    assert any(error.floor_id == str(floor_2.id) for error in result.errors)


def test_later_floor_below_earlier_is_detected(db_session: Session):
    building = factories.building_factory(db_session)
    floor_1 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("4.0"),
    )
    floor_2 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=2,
        elevation_min=Decimal("-1.0"),
        elevation_max=Decimal("3.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is False
    inconsistent = [error for error in result.errors if error.code == "ELEVATION_INCONSISTENT"]
    assert inconsistent
    assert any(error.floor_id == str(floor_2.id) for error in inconsistent)
    assert not any(error.floor_id == str(floor_1.id) for error in inconsistent)


def test_duplicate_floor_number_is_detected(db_session: Session):
    building = factories.building_factory(db_session)
    factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is False
    assert any(error.code == "ELEVATION_INCONSISTENT" for error in result.errors)


def test_unit_outside_floor_is_detected(db_session: Session):
    building = factories.building_factory(db_session)
    floor = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    unit = factories.unit_factory(
        db_session,
        floor=floor,
        z_min=Decimal("-1.0"),
        z_max=Decimal("2.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is False
    assert any(error.code == "UNIT_OUTSIDE_FLOOR" for error in result.errors)
    assert any(error.unit_id == str(unit.id) for error in result.errors)


def test_unit_spanning_floors_is_detected(db_session: Session):
    building = factories.building_factory(db_session)
    floor_1 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    factories.floor_factory(
        db_session,
        building=building,
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )
    unit = factories.unit_factory(
        db_session,
        floor=floor_1,
        z_min=Decimal("2.0"),
        z_max=Decimal("4.0"),
    )

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is False
    assert any(error.code == "UNIT_SPANS_FLOORS" for error in result.errors)
    assert any(error.unit_id == str(unit.id) for error in result.errors)


def test_nonexistent_building_raises_value_error(db_session: Session):
    missing_id = uuid.uuid4()
    try:
        validate_elevation_consistency(db_session, missing_id)
    except ValueError as exc:
        assert str(exc) == "Building not found"
    else:
        raise AssertionError("Expected ValueError for nonexistent building")


def test_empty_building_is_valid(db_session: Session):
    building = factories.building_factory(db_session)

    result = validate_elevation_consistency(db_session, building.id)

    assert result.valid is True
    assert result.errors == []


def test_repeated_validation_is_deterministic(db_session: Session):
    building = factories.building_factory(db_session)
    floor_1 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("4.0"),
    )
    floor_2 = factories.floor_factory(
        db_session,
        building=building,
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )
    factories.unit_factory(
        db_session,
        floor=floor_1,
        z_min=Decimal("0.0"),
        z_max=Decimal("3.0"),
    )
    factories.unit_factory(
        db_session,
        floor=floor_2,
        z_min=Decimal("0.0"),
        z_max=Decimal("3.0"),
    )

    first = validate_elevation_consistency(db_session, building.id)
    second = validate_elevation_consistency(db_session, building.id)

    assert first.model_dump() == second.model_dump()

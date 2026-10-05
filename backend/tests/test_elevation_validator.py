from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.building import Building
from app.models.floor import Floor, FloorType
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.elevation import ElevationValidationResult
from app.validators.elevation_validator import (
    _compute_elevation_errors,
    validate_elevation_consistency,
)


def _make_floor(
    *,
    floor_id: uuid.UUID | None = None,
    floor_number: int,
    elevation_min: Decimal,
    elevation_max: Decimal,
) -> Floor:
    return Floor(
        id=floor_id or uuid.uuid4(),
        building_id=uuid.uuid4(),
        floor_number=floor_number,
        level_name=f"Level {floor_number}",
        floor_type=FloorType.GROUND,
        elevation_min=elevation_min,
        elevation_max=elevation_max,
    )


def _make_unit(
    *,
    unit_id: uuid.UUID | None = None,
    floor_id: uuid.UUID,
    z_min: Decimal,
    z_max: Decimal,
) -> PropertyGeometry:
    geometry_id = uuid.uuid4()
    unit_id = unit_id or uuid.uuid4()
    return PropertyGeometry(
        id=geometry_id,
        unit_id=unit_id,
        x_min=Decimal("0.0"),
        x_max=Decimal("5.0"),
        y_min=Decimal("0.0"),
        y_max=Decimal("5.0"),
        z_min=z_min,
        z_max=z_max,
        geometry_type=GeometryType.AABB,
    )


def test_same_floor_units_with_identical_ranges_are_valid():
    floor = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    units = [
        _make_unit(floor_id=floor.id, z_min=Decimal("0.0"), z_max=Decimal("3.0")),
        _make_unit(floor_id=floor.id, z_min=Decimal("0.0"), z_max=Decimal("3.0")),
    ]

    errors = _compute_elevation_errors([floor], {floor.id: units})

    assert errors == []


def test_same_floor_units_with_different_ranges_raise_elevation_inconsistent():
    floor = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    units = [
        _make_unit(floor_id=floor.id, z_min=Decimal("0.0"), z_max=Decimal("3.0")),
        _make_unit(floor_id=floor.id, z_min=Decimal("0.0"), z_max=Decimal("2.0")),
    ]

    errors = _compute_elevation_errors([floor], {floor.id: units})

    assert [error.code for error in errors] == ["ELEVATION_INCONSISTENT"]
    assert errors[0].floor_id == str(floor.id)


def test_adjacent_floors_touching_are_not_overlap():
    floor1 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    floor2 = _make_floor(
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )

    errors = _compute_elevation_errors([floor1, floor2], {floor1.id: [], floor2.id: []})

    assert not any(error.code == "FLOOR_OVERLAP" for error in errors)


def test_overlapping_floors_raise_floor_overlap():
    floor1 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("4.0"),
    )
    floor2 = _make_floor(
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )

    errors = _compute_elevation_errors([floor1, floor2], {floor1.id: [], floor2.id: []})

    assert [error.code for error in errors] == ["FLOOR_OVERLAP", "FLOOR_OVERLAP"]
    assert {error.floor_id for error in errors} == {str(floor1.id), str(floor2.id)}


def test_later_floor_below_earlier_raises_elevation_inconsistent():
    floor1 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("5.0"),
    )
    floor2 = _make_floor(
        floor_number=2,
        elevation_min=Decimal("-1.0"),
        elevation_max=Decimal("4.0"),
    )

    errors = _compute_elevation_errors([floor1, floor2], {floor1.id: [], floor2.id: []})

    assert any(error.code == "ELEVATION_INCONSISTENT" for error in errors)
    assert any(error.floor_id == str(floor2.id) for error in errors)


def test_duplicate_floor_number_raises_elevation_inconsistent():
    floor1 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    floor2 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )

    errors = _compute_elevation_errors([floor1, floor2], {floor1.id: [], floor2.id: []})

    assert any(error.code == "ELEVATION_INCONSISTENT" for error in errors)


def test_unit_below_parent_floor_raises_unit_outside_floor():
    floor = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    unit = _make_unit(floor_id=floor.id, z_min=Decimal("-1.0"), z_max=Decimal("2.0"))

    errors = _compute_elevation_errors([floor], {floor.id: [unit]})

    assert [error.code for error in errors] == ["UNIT_OUTSIDE_FLOOR"]
    assert errors[0].floor_id == str(floor.id)
    assert errors[0].unit_id == str(unit.unit_id)


def test_unit_above_parent_floor_raises_unit_outside_floor():
    floor = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    unit = _make_unit(floor_id=floor.id, z_min=Decimal("2.0"), z_max=Decimal("4.0"))

    errors = _compute_elevation_errors([floor], {floor.id: [unit]})

    assert [error.code for error in errors] == ["UNIT_OUTSIDE_FLOOR"]


def test_unit_intersects_two_floors_raises_unit_spans_floors():
    floor1 = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    floor2 = _make_floor(
        floor_number=2,
        elevation_min=Decimal("3.0"),
        elevation_max=Decimal("6.0"),
    )
    unit = _make_unit(floor_id=floor1.id, z_min=Decimal("2.0"), z_max=Decimal("4.0"))

    errors = _compute_elevation_errors([floor1, floor2], {floor1.id: [unit], floor2.id: []})

    assert [error.code for error in errors] == ["UNIT_SPANS_FLOORS"]
    assert errors[0].unit_id == str(unit.unit_id)


def test_unit_exactly_fills_parent_floor_is_valid():
    floor = _make_floor(
        floor_number=1,
        elevation_min=Decimal("0.0"),
        elevation_max=Decimal("3.0"),
    )
    unit = _make_unit(floor_id=floor.id, z_min=Decimal("0.0"), z_max=Decimal("3.0"))

    errors = _compute_elevation_errors([floor], {floor.id: [unit]})

    assert errors == []


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalarRows(self._rows)


class _FakeScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, *, building=None, floors=None, units=None):
        self._building = building
        self._floors = floors or []
        self._units = units or []

    def get(self, model, key):
        if self._building is None:
            return None
        if key == self._building.id:
            return self._building
        return None

    def execute(self, query):
        return _FakeResult(self._floors)


def test_validate_elevation_consistency_raises_for_nonexistent_building():
    db = _FakeSession(building=None)
    with pytest.raises(ValueError, match="Building not found"):
        validate_elevation_consistency(db, uuid.uuid4())


def test_validate_elevation_consistency_returns_valid_for_empty_building():
    building = Building(
        id=uuid.uuid4(),
        parcel_id=uuid.uuid4(),
        building_identifier="BLDG-EMPTY",
        name="Empty",
        building_type="residential",
        construction_status="completed",
    )
    db = _FakeSession(building=building, floors=[])

    result = validate_elevation_consistency(db, building.id)

    assert result == ElevationValidationResult(valid=True, errors=[])

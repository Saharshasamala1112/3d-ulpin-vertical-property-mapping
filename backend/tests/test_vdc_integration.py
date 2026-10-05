"""Unit tests for the W19 VDC integration resolvers.

These cover the segment-derivation rules directly, including the edges that are
awkward to reach through the API (absent parents, non-numeric floor numbers,
unrepresentable levels). The integration suite covers the end-to-end path.

The models below are real ORM instances that are never added to a session, so
nothing is written; only the attributes the resolvers read are populated.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType
from app.models.floor import Floor, FloorType
from app.models.parcel import Parcel
from app.models.unit import Unit
from app.services.vdc_generator import generate_vdc
from app.services.vdc_integration import (
    DOMAIN_BY_BUILDING_TYPE,
    resolve_domain,
    resolve_level,
    resolve_ulpin,
    resolve_unit_segment,
    vdc_for_unit,
)

#: The resolvers never query when a floor is supplied, so this session is never
#: used for IO; it exists only to satisfy the signature.
_UNUSED_SESSION = Session()


def _floor(floor_type: Any, floor_number: Any) -> Floor:
    return Floor(
        id=uuid.uuid4(),
        floor_type=floor_type,
        floor_number=floor_number,
    )


def _hierarchy(
    *,
    ulpin: str | None = "GEOSX12345",
    building_type: BuildingType = BuildingType.RESIDENTIAL,
    floor_type: FloorType = FloorType.TYPICAL,
    floor_number: Any = 1,
    unit_identifier: str | None = "U101",
) -> tuple[Unit, Floor]:
    parcel = Parcel(id=uuid.uuid4(), ulpin=ulpin)
    building = Building(id=uuid.uuid4(), building_type=building_type, parcel=parcel)
    floor = Floor(
        id=uuid.uuid4(),
        floor_type=floor_type,
        floor_number=floor_number,
        building=building,
    )
    unit = Unit(id=uuid.uuid4(), unit_identifier=unit_identifier, floor=floor)
    return unit, floor


# --------------------------------------------------------------------------
# resolve_domain
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("building_type", "expected"),
    [
        (BuildingType.RESIDENTIAL, "A"),
        (BuildingType.COMMERCIAL, "B"),
        (BuildingType.INDUSTRIAL, "C"),
        (BuildingType.INSTITUTIONAL, "D"),
        (BuildingType.MIXED_USE, None),
    ],
)
def test_resolve_domain_maps_every_building_type(building_type, expected) -> None:
    assert resolve_domain(building_type) == expected


def test_resolve_domain_covers_whole_enum() -> None:
    assert set(DOMAIN_BY_BUILDING_TYPE) == set(BuildingType)


def test_resolve_domain_without_building_type() -> None:
    assert resolve_domain(None) is None


def test_resolve_domain_unknown_value() -> None:
    assert resolve_domain(cast(Any, "not-a-building-type")) is None


# --------------------------------------------------------------------------
# resolve_level
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("floor_type", "floor_number", "expected"),
    [
        (FloorType.GROUND, 1, 0),
        (FloorType.GROUND, 0, 0),
        (FloorType.TYPICAL, 1, 1),
        (FloorType.TYPICAL, 12, 12),
        (FloorType.PENTHOUSE, 5, 5),
        (FloorType.ROOFTOP, 22, 22),
        (FloorType.BASEMENT, 1, -1),
        (FloorType.BASEMENT, 3, -3),
        (FloorType.TYPICAL, 999, 999),
    ],
)
def test_resolve_level_signs(floor_type, floor_number, expected) -> None:
    assert resolve_level(_floor(floor_type, floor_number)) == expected


@pytest.mark.parametrize(
    ("floor_type", "floor_number"),
    [
        (FloorType.BASEMENT, 0),
        (FloorType.TYPICAL, 1000),
        (FloorType.PENTHOUSE, 1000),
        (FloorType.ROOFTOP, 1001),
        (FloorType.BASEMENT, 1000),
    ],
)
def test_resolve_level_rejects_unrepresentable(floor_type, floor_number) -> None:
    assert resolve_level(_floor(floor_type, floor_number)) is None


def test_resolve_level_without_floor() -> None:
    assert resolve_level(None) is None


def test_resolve_level_without_floor_type() -> None:
    assert resolve_level(_floor(None, 1)) is None


def test_resolve_level_without_floor_number() -> None:
    assert resolve_level(_floor(FloorType.TYPICAL, None)) is None


def test_resolve_level_non_numeric_floor_number() -> None:
    assert resolve_level(_floor(FloorType.TYPICAL, "first")) is None


def test_resolve_level_unknown_floor_type() -> None:
    """A floor type outside the convention yields None rather than a guessed level."""
    assert resolve_level(_floor(cast(Any, "mezzanine"), 3)) is None


# --------------------------------------------------------------------------
# resolve_ulpin / resolve_unit_segment
# --------------------------------------------------------------------------


def test_resolve_ulpin_reads_parcel_ulpin_verbatim() -> None:
    assert resolve_ulpin(Parcel(id=uuid.uuid4(), ulpin="GEOSX12345")) == "GEOSX12345"
    assert resolve_ulpin(Parcel(id=uuid.uuid4(), ulpin="ULPIN-0001")) == "ULPIN-0001"


def test_resolve_ulpin_without_parcel_or_value() -> None:
    assert resolve_ulpin(None) is None
    assert resolve_ulpin(Parcel(id=uuid.uuid4(), ulpin=None)) is None


def test_resolve_unit_segment_passes_identifier_through() -> None:
    assert resolve_unit_segment("U101") == "U101"
    assert resolve_unit_segment("1") == "1"
    assert resolve_unit_segment("unit-101") == "unit-101"


@pytest.mark.parametrize("value", [None, "", " U101", "U101 ", 101])
def test_resolve_unit_segment_rejects_unusable(value) -> None:
    assert resolve_unit_segment(value) is None


# --------------------------------------------------------------------------
# vdc_for_unit
# --------------------------------------------------------------------------


def test_vdc_for_unit_generates_canonical_code() -> None:
    unit, floor = _hierarchy()
    code = vdc_for_unit(_UNUSED_SESSION, unit, floor=floor)
    assert code == generate_vdc("GEOSX12345", "A", 1, "U101")


def test_vdc_for_unit_loads_floor_from_unit_when_not_supplied() -> None:
    unit, floor = _hierarchy()
    unit.floor = floor
    assert vdc_for_unit(_UNUSED_SESSION, unit) == generate_vdc("GEOSX12345", "A", 1, "U101")


@pytest.mark.parametrize(
    "overrides",
    [
        {"ulpin": None},
        {"ulpin": "ULPIN-0001"},
        {"building_type": BuildingType.MIXED_USE},
        {"floor_type": FloorType.BASEMENT, "floor_number": 0},
        {"floor_type": FloorType.TYPICAL, "floor_number": 1000},
        {"unit_identifier": None},
        {"unit_identifier": "unit-101"},
        {"unit_identifier": "U1234567"},
    ],
)
def test_vdc_for_unit_returns_none_when_not_encodable(overrides) -> None:
    unit, floor = _hierarchy(**overrides)
    assert vdc_for_unit(_UNUSED_SESSION, unit, floor=floor) is None


def test_vdc_for_unit_without_floor() -> None:
    unit = Unit(id=uuid.uuid4(), unit_identifier="U101", floor=None)
    assert vdc_for_unit(_UNUSED_SESSION, unit) is None


def test_vdc_for_unit_without_unit() -> None:
    assert vdc_for_unit(_UNUSED_SESSION, cast(Any, None)) is None


def test_vdc_for_unit_without_building() -> None:
    unit = Unit(id=uuid.uuid4(), unit_identifier="U101")
    floor = Floor(id=uuid.uuid4(), floor_type=FloorType.TYPICAL, floor_number=1, building=None)
    assert vdc_for_unit(_UNUSED_SESSION, unit, floor=floor) is None

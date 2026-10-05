"""Unit CRUD against a real PostgreSQL database.

Includes the regression test for the ``UnitType`` / ``UnitStatus``
``values_callable`` fix, and covers the VDC lookup endpoint.

Work Item #19 adds automatic VDC generation on create, regeneration when the
unit identifier changes, and the parsed segments returned by the VDC endpoint.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.building import BuildingType
from app.models.floor import Floor, FloorType
from app.models.geometry3d import PropertyGeometry
from app.models.unit import Unit, UnitStatus, UnitType
from app.services.vdc_generator import generate_vdc
from app.validators.vdc_parser import parse_vdc, validate_vdc
from tests.integration import factories

pytestmark = pytest.mark.integration


def _payload(**overrides) -> dict:
    payload = {
        "unit_identifier": "UNIT-TEST-0001",
        "unit_type": "residential",
        "area_sqm": 75.0,
        "x_min": 0.0,
        "x_max": 5.0,
        "y_min": 0.0,
        "y_max": 5.0,
        "z_min": 0.0,
        "z_max": 3.0,
        "status": "active",
        "vdc_code": "VDC-TEST-0001",
    }
    payload.update(overrides)
    return payload


def _vdc_payload(**overrides) -> dict:
    """A create payload whose unit identifier is a valid VDC segment.

    No ``vdc_code`` is supplied, so a stored code can only come from generation.
    """
    payload = {
        "unit_identifier": "U101",
        "unit_type": "residential",
        "area_sqm": 75.0,
        "x_min": 0.0,
        "x_max": 5.0,
        "y_min": 0.0,
        "y_max": 5.0,
        "z_min": 0.0,
        "z_max": 3.0,
        "status": "active",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------


def test_create_unit_persists_row(client: TestClient, db_session: Session, floor: Floor) -> None:
    """POST /floors/{id}/units returns 201 and stores the unit."""
    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["floor_id"] == str(floor.id)
    assert body["unit_type"] == "residential"
    assert body["status"] == "active"
    assert body["area_sqm"] == 75.0

    stored = db_session.get(Unit, body["id"])
    assert stored is not None
    assert stored.unit_type is UnitType.RESIDENTIAL
    assert stored.status is UnitStatus.ACTIVE
    # W19: this hierarchy carries no spec-valid ULPIN, "UNIT-TEST-0001" is not a
    # valid unit segment, and the supplied "VDC-TEST-0001" is not a valid VDC, so
    # nothing is encodable and the invalid placeholder is dropped rather than stored.
    assert stored.vdc_code is None
    geometry = db_session.query(PropertyGeometry).filter_by(unit_id=stored.id).one()
    assert geometry.x_min == 0
    assert geometry.x_max == 5
    geometry_response = client.get(f"/api/v1/units/{stored.id}/geometry")
    assert geometry_response.status_code == 200, geometry_response.text
    assert float(geometry_response.json()["x_max"]) == 5.0


def test_create_unit_unknown_floor(client: TestClient) -> None:
    """Creating under an unknown floor returns 404."""
    response = client.post(f"/api/v1/floors/{uuid.uuid4()}/units", json=_payload())

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["details"], dict)


def test_create_unit_validates_body(client: TestClient, floor: Floor) -> None:
    """A non-positive area is rejected."""
    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_payload(area_sqm=0))

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "area_sqm" in body["details"]


def test_create_unit_rejects_invalid_type(client: TestClient, floor: Floor) -> None:
    """An unsupported unit_type is rejected by the schema pattern."""
    response = client.post(
        f"/api/v1/floors/{floor.id}/units",
        json=_payload(unit_type="submarine"),
    )

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_create_unit_rejects_invalid_status(client: TestClient, floor: Floor) -> None:
    """An unsupported status is rejected by the schema pattern."""
    response = client.post(
        f"/api/v1/floors/{floor.id}/units",
        json=_payload(status="haunted"),
    )

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# READ
# --------------------------------------------------------------------------


def test_get_unit(client: TestClient, unit: Unit) -> None:
    """GET /units/{id} returns the unit."""
    response = client.get(f"/api/v1/units/{unit.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(unit.id)
    assert body["unit_type"] == "residential"
    assert body["z_max"] == 3.0


def test_get_unit_not_found(client: TestClient) -> None:
    """An unknown unit id returns 404."""
    response = client.get(f"/api/v1/units/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_list_units_for_floor(client: TestClient, db_session: Session, floor: Floor) -> None:
    """GET /floors/{id}/units lists only that floor's units."""
    factories.unit_factory(db_session, floor=floor, unit_identifier="U-1")
    factories.unit_factory(db_session, floor=floor, unit_identifier="U-2")
    other_floor = factories.floor_factory(db_session)
    factories.unit_factory(db_session, floor=other_floor, unit_identifier="U-99")

    response = client.get(f"/api/v1/floors/{floor.id}/units")

    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["unit_identifier"] for item in body} == {"U-1", "U-2"}


def test_list_units_unknown_floor(client: TestClient) -> None:
    """Listing under an unknown floor returns 404."""
    response = client.get(f"/api/v1/floors/{uuid.uuid4()}/units")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------


def test_update_unit(client: TestClient, db_session: Session, unit: Unit) -> None:
    """PUT /units/{id} applies and stores the update."""
    response = client.put(
        f"/api/v1/units/{unit.id}",
        json={"unit_type": "commercial", "status": "leased", "area_sqm": 120.0},
    )

    assert response.status_code == 200, response.text
    assert response.json()["unit_type"] == "commercial"
    assert response.json()["status"] == "leased"

    db_session.expire_all()
    stored = db_session.get(Unit, unit.id)
    assert stored is not None
    assert stored.unit_type is UnitType.COMMERCIAL
    assert stored.status is UnitStatus.LEASED
    assert float(stored.area_sqm) == 120.0
    geometry = db_session.query(PropertyGeometry).filter_by(unit_id=stored.id).one()
    assert float(geometry.x_max) == 5.0


def test_update_unit_not_found(client: TestClient) -> None:
    """Updating an unknown unit returns 404."""
    response = client.put(f"/api/v1/units/{uuid.uuid4()}", json={"area_sqm": 10.0})

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_update_unit_rejects_equal_bounds(client: TestClient, unit: Unit) -> None:
    response = client.put(f"/api/v1/units/{unit.id}", json={"x_min": 5.0})

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_update_unit_rejects_invalid_status(client: TestClient, unit: Unit) -> None:
    """An unsupported status is rejected on update too."""
    response = client.put(f"/api/v1/units/{unit.id}", json={"status": "on_fire"})

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_unit_bbox_update_is_read_through_geometry_api(client: TestClient, unit: Unit) -> None:
    updated = client.put(f"/api/v1/units/{unit.id}", json={"x_max": 8.0})

    assert updated.status_code == 200, updated.text
    geometry = client.get(f"/api/v1/units/{unit.id}/geometry")

    assert geometry.status_code == 200, geometry.text
    assert float(geometry.json()["x_max"]) == 8.0


# --------------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------------


def test_delete_unit_soft_deletes_by_archiving(
    client: TestClient, db_session: Session, unit: Unit
) -> None:
    """DELETE /units/{id} returns 204 and archives the unit (soft delete)."""
    unit_id = unit.id
    response = client.delete(f"/api/v1/units/{unit_id}")

    assert response.status_code == 204, response.text
    db_session.expire_all()
    stored = db_session.get(Unit, unit_id)
    assert stored is not None, "units are soft-deleted, the row must still exist"
    assert stored.status is UnitStatus.ARCHIVED


def test_delete_unit_not_found(client: TestClient) -> None:
    """Deleting an unknown unit returns 404."""
    response = client.delete(f"/api/v1/units/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# VDC
# --------------------------------------------------------------------------


def test_get_vdc_returns_code(client: TestClient, unit: Unit) -> None:
    """GET /units/{id}/vdc returns the stored VDC code."""
    response = client.get(f"/api/v1/units/{unit.id}/vdc")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unit_id"] == str(unit.id)
    assert body["vdc_code"] == unit.vdc_code
    assert body["status"] == "present"
    _assert_valid(body["vdc_code"])


def test_get_vdc_null_when_unassigned(
    client: TestClient, db_session: Session, floor: Floor
) -> None:
    """A unit with no VDC code returns 200 with a null code."""
    unit = factories.unit_factory(db_session, floor=floor, vdc_code=None)

    response = client.get(f"/api/v1/units/{unit.id}/vdc")

    assert response.status_code == 200, response.text
    assert response.json()["vdc_code"] is None
    assert response.json()["status"] == "missing"


def test_get_vdc_not_found(client: TestClient) -> None:
    """Requesting a VDC for an unknown unit returns 404."""
    response = client.get(f"/api/v1/units/{uuid.uuid4()}/vdc")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# Enum regression (the values_callable fix)
# --------------------------------------------------------------------------


def test_unit_enums_round_trip_through_postgres(
    client: TestClient, db_session: Session, floor: Floor
) -> None:
    """Every unit_type and status survives a real write/read cycle.

    Regression guard for the ``values_callable`` fix on both ``UnitType`` and
    ``UnitStatus``: without it the ORM bound ``RESIDENTIAL`` / ``PLANNED`` and
    PostgreSQL rejected them, and reading lowercase rows back raised
    ``LookupError``.
    """
    for unit_type in UnitType:
        for status in UnitStatus:
            response = client.post(
                f"/api/v1/floors/{floor.id}/units",
                json=_payload(
                    unit_identifier=f"ENUM-{unit_type.value}-{status.value}",
                    unit_type=unit_type.value,
                    status=status.value,
                ),
            )
            assert response.status_code == 201, response.text
            unit_id = response.json()["id"]

            db_session.expire_all()
            stored = db_session.get(Unit, unit_id)
            assert stored is not None, f"{unit_type.value}/{status.value} was not stored"
            assert stored.unit_type is unit_type
            assert stored.status is status

            read = client.get(f"/api/v1/units/{unit_id}")
            assert read.status_code == 200, read.text
            assert read.json()["unit_type"] == unit_type.value
            assert read.json()["status"] == status.value


# --------------------------------------------------------------------------
# W19: automatic VDC generation
# --------------------------------------------------------------------------


def _assert_valid(code: str) -> None:
    assert code is not None, "expected a generated VDC"
    assert validate_vdc(code) == [], f"{code} failed validation: {validate_vdc(code)}"


def test_create_unit_generates_vdc_for_valid_hierarchy(
    client: TestClient, db_session: Session, vdc_floor: Floor, vdc_parcel
) -> None:
    """A fully valid hierarchy yields a canonical VDC in the response and the row."""
    response = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())

    assert response.status_code == 201, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    parsed = parse_vdc(code)
    assert parsed.ulpin == vdc_parcel.ulpin
    assert parsed.domain == "A"
    assert parsed.level == "F1"
    assert parsed.unit == "U101"

    db_session.expire_all()
    stored = db_session.get(Unit, response.json()["id"])
    assert stored is not None
    assert stored.vdc_code == code


def test_get_vdc_returns_parsed_segments(client: TestClient, vdc_floor: Floor, vdc_parcel) -> None:
    """GET /units/{id}/vdc returns the stored code split into its five segments."""
    created = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    unit_id = created.json()["id"]

    response = client.get(f"/api/v1/units/{unit_id}/vdc")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unit_id"] == unit_id
    assert body["vdc_code"] == created.json()["vdc_code"]
    assert body["ulpin"] == vdc_parcel.ulpin
    assert body["domain"] == "A"
    assert body["level"] == "F1"
    assert body["unit"] == "U101"
    assert body["checksum"] is not None
    assert body["status"] == "present"


def test_get_vdc_is_read_only(client: TestClient, db_session: Session, vdc_unit: Unit) -> None:
    """The endpoint never generates a code for a unit that has none."""
    assert vdc_unit.vdc_code is None

    response = client.get(f"/api/v1/units/{vdc_unit.id}/vdc")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vdc_code"] is None
    assert body["status"] == "missing"
    for segment in ("ulpin", "domain", "level", "unit", "checksum"):
        assert body[segment] is None
    db_session.expire_all()
    stored = db_session.get(Unit, vdc_unit.id)
    assert stored is not None
    assert stored.vdc_code is None


def test_generated_code_is_idempotent(client: TestClient, vdc_floor: Floor, vdc_parcel) -> None:
    """Two units with the same identifier on the same hierarchy get the same code."""
    first = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    second = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["vdc_code"] == second.json()["vdc_code"]

    # Repeated reads are stable too.
    reads = [client.get(f"/api/v1/units/{first.json()['id']}/vdc").json() for _ in range(2)]
    assert reads[0] == reads[1]


def test_generate_vdc_endpoint_persists_valid_code_idempotently(
    client: TestClient, db_session: Session, vdc_unit: Unit
) -> None:
    """The unit-scoped endpoint derives and persists a validated code without segments."""
    response = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")

    assert response.status_code == 200, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    assert response.json()["status"] == "present"
    assert parse_vdc(code).unit == vdc_unit.unit_identifier
    validation = client.post("/api/v1/vdc/validate", json={"vdc": code})
    assert validation.status_code == 200
    assert validation.json() == {"valid": True, "errors": []}

    db_session.expire_all()
    stored = db_session.get(Unit, vdc_unit.id)
    assert stored is not None
    assert stored.vdc_code == code
    updated_at = stored.updated_at

    repeated = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["vdc_code"] == code
    db_session.expire_all()
    assert db_session.get(Unit, vdc_unit.id).updated_at == updated_at


def test_update_identifier_regenerates_vdc(
    client: TestClient, db_session: Session, vdc_unit
) -> None:
    """Changing unit_identifier re-encodes the unit segment."""
    assert vdc_unit.vdc_code is None

    response = client.put(f"/api/v1/units/{vdc_unit.id}", json={"unit_identifier": "U205"})

    assert response.status_code == 200, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    assert parse_vdc(code).unit == "U205"
    assert parse_vdc(code).level == "F1"

    db_session.expire_all()
    stored = db_session.get(Unit, vdc_unit.id)
    assert stored is not None
    assert stored.vdc_code == code
    assert response.json()["vdc_status"] == "present"


def test_floor_reassignment_regenerates_vdc(
    client: TestClient, db_session: Session, vdc_unit: Unit, vdc_floor: Floor
) -> None:
    new_floor = factories.floor_factory(
        db_session,
        building=vdc_floor.building,
        floor_number=2,
        floor_type=FloorType.TYPICAL,
    )

    response = client.put(f"/api/v1/units/{vdc_unit.id}", json={"floor_id": str(new_floor.id)})

    assert response.status_code == 200, response.text
    assert response.json()["floor_id"] == str(new_floor.id)
    assert response.json()["vdc_status"] == "present"
    assert parse_vdc(response.json()["vdc_code"]).level == "F2"
    assert parse_vdc(response.json()["vdc_code"]).unit == vdc_unit.unit_identifier


def test_parent_vdc_inputs_mark_code_stale_until_refreshed(
    client: TestClient, db_session: Session, vdc_unit: Unit, vdc_floor: Floor, vdc_parcel
) -> None:
    generated = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert generated.status_code == 200, generated.text
    original = generated.json()["vdc_code"]

    vdc_parcel.ulpin = "GEOSX54321"
    db_session.flush()
    assert client.get(f"/api/v1/units/{vdc_unit.id}").json()["vdc_status"] == "stale"
    refreshed = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["vdc_code"] != original

    vdc_floor.building.building_type = BuildingType.COMMERCIAL
    db_session.flush()
    assert client.get(f"/api/v1/units/{vdc_unit.id}").json()["vdc_status"] == "stale"
    refreshed = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert refreshed.status_code == 200, refreshed.text
    assert parse_vdc(refreshed.json()["vdc_code"]).domain == "B"

    vdc_floor.floor_number = 2
    db_session.flush()
    assert client.get(f"/api/v1/units/{vdc_unit.id}").json()["vdc_status"] == "stale"
    refreshed = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert refreshed.status_code == 200, refreshed.text
    assert parse_vdc(refreshed.json()["vdc_code"]).level == "F2"


def test_vdc_generation_unavailable_returns_422_without_overwriting(
    client: TestClient, db_session: Session, vdc_unit: Unit, vdc_floor: Floor
) -> None:
    created = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")
    assert created.status_code == 200, created.text
    existing = created.json()["vdc_code"]
    vdc_floor.building.building_type = BuildingType.MIXED_USE
    db_session.flush()

    response = client.post(f"/api/v1/units/{vdc_unit.id}/vdc")

    assert response.status_code == 422, response.text
    db_session.expire_all()
    stored = db_session.get(Unit, vdc_unit.id)
    assert stored is not None
    assert stored.vdc_code == existing


def test_non_vdc_update_leaves_code_unchanged(
    client: TestClient, db_session: Session, vdc_floor: Floor
) -> None:
    """A unit_type or geometry change never touches a stored code."""
    created = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    unit_id = created.json()["id"]
    original = created.json()["vdc_code"]

    response = client.put(
        f"/api/v1/units/{unit_id}",
        json={"unit_type": "commercial", "x_max": 8.0, "area_sqm": 90.0},
    )

    assert response.status_code == 200, response.text
    assert response.json()["vdc_code"] == original
    db_session.expire_all()
    stored = db_session.get(Unit, unit_id)
    assert stored is not None
    assert stored.vdc_code == original


def test_invalid_identifier_stores_no_vdc(
    client: TestClient, db_session: Session, vdc_floor
) -> None:
    """Identifiers outside ``[A-Z1-9][A-Z0-9]{0,5}`` are rejected, never repaired."""
    # A leading zero only disqualifies an identifier that *starts* with one, so
    # "0101" is invalid while "U0101" is not (see the test below).
    for bad in ("unit-101", "UNIT-101", "U1234567", " U101", "0101", "U-101"):
        response = client.post(
            f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload(unit_identifier=bad)
        )
        assert response.status_code == 201, response.text
        assert response.json()["vdc_code"] is None, f"{bad} should not be encodable"

    db_session.expire_all()
    assert db_session.query(Unit).filter(Unit.vdc_code.isnot(None)).count() == 0


def test_identifier_starting_with_a_letter_allows_zeroes(
    client: TestClient, vdc_floor: Floor
) -> None:
    """ "U0101" is a legal unit segment: only a leading zero is rejected."""
    response = client.post(
        f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload(unit_identifier="U0101")
    )

    assert response.status_code == 201, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    assert parse_vdc(code).unit == "U0101"


def test_unmapped_domain_stores_no_vdc(client: TestClient, db_session: Session, vdc_parcel) -> None:
    """MIXED_USE has no domain letter, so the whole chain is unencodable."""
    building = factories.building_factory(
        db_session, parcel=vdc_parcel, building_type=BuildingType.MIXED_USE
    )
    floor = factories.floor_factory(db_session, building=building)

    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_vdc_payload())

    assert response.status_code == 201, response.text
    assert response.json()["vdc_code"] is None


@pytest.mark.parametrize(
    ("building_type", "expected_domain"),
    [
        (BuildingType.RESIDENTIAL, "A"),
        (BuildingType.COMMERCIAL, "B"),
        (BuildingType.INDUSTRIAL, "C"),
        (BuildingType.INSTITUTIONAL, "D"),
    ],
)
def test_domain_comes_from_building_type(
    client: TestClient, db_session: Session, vdc_parcel, building_type, expected_domain
) -> None:
    """DOMAIN is the building's classification, independent of the unit type."""
    building = factories.building_factory(
        db_session, parcel=vdc_parcel, building_type=building_type
    )
    floor = factories.floor_factory(db_session, building=building)

    response = client.post(
        f"/api/v1/floors/{floor.id}/units", json=_vdc_payload(unit_type="parking")
    )

    assert response.status_code == 201, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    assert parse_vdc(code).domain == expected_domain


@pytest.mark.parametrize(
    ("floor_type", "floor_number", "expected_level"),
    [
        (FloorType.GROUND, 1, "G"),
        (FloorType.TYPICAL, 1, "F1"),
        (FloorType.TYPICAL, 12, "F12"),
        (FloorType.PENTHOUSE, 5, "F5"),
        (FloorType.ROOFTOP, 22, "F22"),
        (FloorType.BASEMENT, 1, "B1"),
        (FloorType.BASEMENT, 2, "B2"),
    ],
)
def test_level_convention(
    client: TestClient,
    db_session: Session,
    vdc_building,
    floor_type,
    floor_number,
    expected_level,
) -> None:
    """Floors encode as G, F<n> or B<n> per the W19 convention."""
    floor = factories.floor_factory(
        db_session, building=vdc_building, floor_type=floor_type, floor_number=floor_number
    )

    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_vdc_payload())

    assert response.status_code == 201, response.text
    code = response.json()["vdc_code"]
    _assert_valid(code)
    assert parse_vdc(code).level == expected_level


@pytest.mark.parametrize(
    ("floor_type", "floor_number"),
    [
        (FloorType.BASEMENT, 0),
        (FloorType.TYPICAL, 1000),
        (FloorType.BASEMENT, 1000),
    ],
)
def test_unrepresentable_level_stores_no_vdc(
    client: TestClient, db_session: Session, vdc_building, floor_type, floor_number
) -> None:
    """A level with no valid spelling leaves the code null rather than guessing."""
    floor = factories.floor_factory(
        db_session, building=vdc_building, floor_type=floor_type, floor_number=floor_number
    )

    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_vdc_payload())

    assert response.status_code == 201, response.text
    assert response.json()["vdc_code"] is None


def test_non_geosx_ulpin_stores_no_vdc(
    client: TestClient, db_session: Session, vdc_building
) -> None:
    """A ULPIN that is not ``GEOSX`` + five digits cannot anchor a code.

    ``parcels.ulpin`` is NOT NULL, so a parcel always has some ULPIN; a
    non-conforming one must be rejected rather than coerced into a code.
    """
    parcel = vdc_building.parcel
    parcel.ulpin = "ULPIN-0001"
    db_session.flush()
    floor = factories.floor_factory(
        db_session, building=vdc_building, floor_type=FloorType.TYPICAL, floor_number=1
    )

    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_vdc_payload())

    assert response.status_code == 201, response.text
    assert response.json()["vdc_code"] is None


def test_generated_code_overrides_supplied_code(
    client: TestClient, db_session: Session, vdc_floor: Floor, vdc_parcel
) -> None:
    """Generation wins over a caller-supplied code, even a valid one."""
    supplied = generate_vdc("GEOSX99999", "D", 1, "U999")

    response = client.post(
        f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload(vdc_code=supplied)
    )

    assert response.status_code == 201, response.text
    code = response.json()["vdc_code"]
    assert code != supplied
    assert parse_vdc(code).ulpin == vdc_parcel.ulpin
    assert parse_vdc(code).domain == "A"


def test_valid_supplied_code_is_ignored_when_generation_impossible(
    client: TestClient, db_session: Session, floor: Floor
) -> None:
    """A valid caller-supplied code is not trusted when the hierarchy cannot be encoded."""
    supplied = generate_vdc("GEOSX12345", "A", 1, "U101")
    assert validate_vdc(supplied) == []

    response = client.post(f"/api/v1/floors/{floor.id}/units", json=_payload(vdc_code=supplied))

    assert response.status_code == 201, response.text
    assert response.json()["vdc_code"] is None
    assert response.json()["vdc_status"] == "missing"

    read = client.get(f"/api/v1/units/{response.json()['id']}/vdc")
    assert read.json()["vdc_code"] is None
    assert read.json()["status"] == "missing"


def test_invalid_supplied_code_is_dropped(
    client: TestClient, db_session: Session, floor: Floor
) -> None:
    """An invalid caller-supplied code is never persisted."""
    for bad in ("VDC-TEST-0001", "GEOSX1234", "GEOSX12345-A-F1-U101", "nonsense"):
        response = client.post(f"/api/v1/floors/{floor.id}/units", json=_payload(vdc_code=bad))
        assert response.status_code == 201, response.text
        assert response.json()["vdc_code"] is None, f"{bad} must not be stored"

    db_session.expire_all()
    assert db_session.query(Unit).filter(Unit.vdc_code.isnot(None)).count() == 0


def test_update_to_invalid_identifier_clears_stale_code(
    client: TestClient, db_session: Session, vdc_floor: Floor
) -> None:
    """A failed regeneration drops the old code instead of keeping a stale one."""
    created = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    unit_id = created.json()["id"]
    original = created.json()["vdc_code"]
    assert original is not None

    response = client.put(f"/api/v1/units/{unit_id}", json={"unit_identifier": "unit-205"})

    assert response.status_code == 200, response.text
    assert response.json()["vdc_code"] is None
    db_session.expire_all()
    stored = db_session.get(Unit, unit_id)
    assert stored is not None
    assert stored.vdc_code is None


def test_update_with_explicit_null_keeps_valid_code(
    client: TestClient, db_session: Session, vdc_floor: Floor
) -> None:
    """Sending no vdc_code during a regeneration still regenerates from the hierarchy."""
    created = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    unit_id = created.json()["id"]

    response = client.put(
        f"/api/v1/units/{unit_id}", json={"unit_identifier": "U101", "vdc_code": None}
    )

    assert response.status_code == 200, response.text
    assert response.json()["vdc_code"] == created.json()["vdc_code"]


def test_invalid_bbox_blocks_vdc_regeneration(
    client: TestClient, db_session: Session, vdc_floor: Floor
) -> None:
    """Bounding-box validation runs before generation, so a rejected update writes nothing."""
    created = client.post(f"/api/v1/floors/{vdc_floor.id}/units", json=_vdc_payload())
    unit_id = created.json()["id"]
    original = created.json()["vdc_code"]

    response = client.put(
        f"/api/v1/units/{unit_id}", json={"unit_identifier": "U205", "x_max": -1.0}
    )

    assert response.status_code == 422, response.text
    db_session.expire_all()
    stored = db_session.get(Unit, unit_id)
    assert stored is not None
    assert stored.unit_identifier == "U101"
    assert stored.vdc_code == original


def test_unparseable_stored_code_is_returned_verbatim(
    client: TestClient, db_session: Session, vdc_floor: Floor
) -> None:
    """A historical, unparseable code stays readable with null segments."""
    unit = factories.unit_factory(db_session, floor=vdc_floor, vdc_code="legacy-bad-code")

    response = client.get(f"/api/v1/units/{unit.id}/vdc")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vdc_code"] == "legacy-bad-code"
    assert body["status"] == "invalid"
    for segment in ("ulpin", "domain", "level", "unit", "checksum"):
        assert body[segment] is None


def test_vdc_audit_reports_invalid_legacy_code(db_session: Session, vdc_floor: Floor) -> None:
    unit = factories.unit_factory(db_session, floor=vdc_floor, vdc_code="legacy-bad-code")

    from app.services.unit import audit_invalid_vdc_codes

    invalid = [entry for entry in audit_invalid_vdc_codes(db_session) if entry[0] == str(unit.id)]
    assert len(invalid) == 1
    assert invalid[0][1] == "legacy-bad-code"
    assert invalid[0][2]

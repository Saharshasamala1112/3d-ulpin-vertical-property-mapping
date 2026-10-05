"""Floor CRUD against a real PostgreSQL database.

Includes the regression test for the ``FloorType`` ``values_callable`` fix.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.floor import Floor, FloorType
from tests.integration import factories

pytestmark = pytest.mark.integration


def _payload(**overrides) -> dict:
    payload = {
        "floor_number": 1,
        "level_name": "Ground",
        "floor_type": "ground",
        "elevation_min": 0.0,
        "elevation_max": 3.0,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------


def test_create_floor_persists_row(
    client: TestClient, db_session: Session, building: Building
) -> None:
    """POST /buildings/{id}/floors returns 201 and stores the floor."""
    response = client.post(f"/api/v1/buildings/{building.id}/floors", json=_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["building_id"] == str(building.id)
    assert body["floor_type"] == "ground"
    assert body["elevation_max"] == 3.0

    stored = db_session.get(Floor, body["id"])
    assert stored is not None
    assert stored.floor_type is FloorType.GROUND
    assert stored.level_name == "Ground"


def test_create_floor_unknown_building(client: TestClient) -> None:
    """Creating under an unknown building returns 404."""
    response = client.post(f"/api/v1/buildings/{uuid.uuid4()}/floors", json=_payload())

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["details"], dict)


def test_create_floor_validates_body(client: TestClient, building: Building) -> None:
    """A non-integer floor_number is rejected."""
    response = client.post(
        f"/api/v1/buildings/{building.id}/floors",
        json=_payload(floor_number="basement"),
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "floor_number" in body["details"]


def test_create_floor_rejects_invalid_type(client: TestClient, building: Building) -> None:
    """An unsupported floor_type is rejected by the schema pattern."""
    response = client.post(
        f"/api/v1/buildings/{building.id}/floors",
        json=_payload(floor_type="mezzanine_of_dreams"),
    )

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# READ
# --------------------------------------------------------------------------


def test_get_floor(client: TestClient, floor: Floor) -> None:
    """GET /floors/{id} returns the floor."""
    response = client.get(f"/api/v1/floors/{floor.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(floor.id)
    assert body["floor_number"] == 1
    assert body["floor_type"] == "ground"


def test_get_floor_not_found(client: TestClient) -> None:
    """An unknown floor id returns 404."""
    response = client.get(f"/api/v1/floors/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_list_floors_for_building(
    client: TestClient, db_session: Session, building: Building
) -> None:
    """GET /buildings/{id}/floors lists only that building's floors."""
    factories.floor_factory(db_session, building=building, floor_number=1)
    factories.floor_factory(db_session, building=building, floor_number=2, level_name="First")
    other_building = factories.building_factory(db_session)
    factories.floor_factory(db_session, building=other_building, floor_number=99)

    response = client.get(f"/api/v1/buildings/{building.id}/floors")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["floor_number"] for item in body] == [1, 2]


def test_list_floors_unknown_building(client: TestClient) -> None:
    """Listing under an unknown building returns 404."""
    response = client.get(f"/api/v1/buildings/{uuid.uuid4()}/floors")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------


def test_update_floor(client: TestClient, db_session: Session, floor: Floor) -> None:
    """PUT /floors/{id} applies and stores the update."""
    response = client.put(
        f"/api/v1/floors/{floor.id}",
        json={"floor_number": 5, "level_name": "Fifth", "floor_type": "typical"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["floor_type"] == "typical"

    db_session.expire_all()
    stored = db_session.get(Floor, floor.id)
    assert stored is not None
    assert stored.floor_number == 5
    assert stored.level_name == "Fifth"
    assert stored.floor_type is FloorType.TYPICAL


def test_update_floor_not_found(client: TestClient) -> None:
    """Updating an unknown floor returns 404."""
    response = client.put(f"/api/v1/floors/{uuid.uuid4()}", json={"floor_number": 2})

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_update_floor_rejects_invalid_type(client: TestClient, floor: Floor) -> None:
    """An unsupported floor_type is rejected on update too."""
    response = client.put(f"/api/v1/floors/{floor.id}", json={"floor_type": "attic_prime"})

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------------


def test_delete_floor(client: TestClient, db_session: Session, floor: Floor) -> None:
    """DELETE /floors/{id} returns 204 and removes the row."""
    floor_id = floor.id
    response = client.delete(f"/api/v1/floors/{floor_id}")

    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.get(Floor, floor_id) is None


def test_delete_floor_not_found(client: TestClient) -> None:
    """Deleting an unknown floor returns 404."""
    response = client.delete(f"/api/v1/floors/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# Enum regression (the values_callable fix)
# --------------------------------------------------------------------------


def test_floor_types_round_trip_through_postgres(
    client: TestClient, db_session: Session, building: Building
) -> None:
    """Every floor_type survives a real write/read cycle as its lowercase label.

    Regression guard for the ``values_callable`` fix: without it the ORM bound
    ``FloorType.GROUND`` as the string ``"GROUND"``, which PostgreSQL rejected
    with ``invalid input value for enum floor_type: "GROUND"``, and reading
    lowercase rows back raised ``LookupError``.
    """
    for floor_type in FloorType:
        response = client.post(
            f"/api/v1/buildings/{building.id}/floors",
            json=_payload(
                floor_type=floor_type.value,
                level_name=floor_type.value.title(),
            ),
        )
        assert response.status_code == 201, response.text
        floor_id = response.json()["id"]

        db_session.expire_all()
        stored = db_session.get(Floor, floor_id)
        assert stored is not None, f"floor_type={floor_type.value} was not stored"
        assert stored.floor_type is floor_type

        read = client.get(f"/api/v1/floors/{floor_id}")
        assert read.status_code == 200, read.text
        assert read.json()["floor_type"] == floor_type.value

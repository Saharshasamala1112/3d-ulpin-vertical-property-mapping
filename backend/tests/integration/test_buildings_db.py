"""Building CRUD against a real PostgreSQL/PostGIS database.

Buildings are nested under parcels for creation and listing, but addressed by
their own id for read/update/delete.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.parcel import Parcel
from tests.integration import factories

pytestmark = pytest.mark.integration

FOOTPRINT = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.51, 12.91],
            [77.59, 12.91],
            [77.59, 12.99],
            [77.51, 12.99],
            [77.51, 12.91],
        ]
    ],
}


def _payload(**overrides) -> dict:
    payload = {
        "building_identifier": "BLDG-TEST-0001",
        "name": "Integration Tower",
        "building_type": "residential",
        "construction_status": "completed",
        "footprint_geometry": FOOTPRINT,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------


def test_create_building_persists_row(
    client: TestClient, db_session: Session, parcel: Parcel
) -> None:
    """POST /parcels/{id}/buildings returns 201 and stores the building."""
    response = client.post(f"/api/v1/parcels/{parcel.id}/buildings", json=_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["parcel_id"] == str(parcel.id)
    assert body["building_type"] == "residential"
    assert body["construction_status"] == "completed"

    stored = db_session.get(Building, body["id"])
    assert stored is not None
    assert stored.building_identifier == "BLDG-TEST-0001"
    assert stored.building_type is BuildingType.RESIDENTIAL
    assert stored.construction_status is ConstructionStatus.COMPLETED


def test_create_building_without_footprint(client: TestClient, parcel: Parcel) -> None:
    """footprint_geometry is optional."""
    response = client.post(
        f"/api/v1/parcels/{parcel.id}/buildings",
        json=_payload(footprint_geometry=None),
    )

    assert response.status_code == 201, response.text
    assert response.json()["footprint_geometry"] is None


def test_create_building_unknown_parcel(client: TestClient) -> None:
    """Creating under an unknown parcel returns 404."""
    response = client.post(f"/api/v1/parcels/{uuid.uuid4()}/buildings", json=_payload())

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["details"], dict)


def test_create_building_rejects_invalid_type(client: TestClient, parcel: Parcel) -> None:
    """An unsupported building_type is rejected by the schema pattern."""
    response = client.post(
        f"/api/v1/parcels/{parcel.id}/buildings",
        json=_payload(building_type="spaceship"),
    )

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_create_building_rejects_invalid_footprint(client: TestClient, parcel: Parcel) -> None:
    """A non-polygon footprint surfaces the service's 422 VALIDATION_ERROR."""
    response = client.post(
        f"/api/v1/parcels/{parcel.id}/buildings",
        json=_payload(footprint_geometry={"type": "Point", "coordinates": [77.5, 12.9]}),
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "footprint" in body["message"].lower() or "polygon" in body["message"].lower()


# --------------------------------------------------------------------------
# READ
# --------------------------------------------------------------------------


def test_get_building(client: TestClient, building: Building) -> None:
    """GET /buildings/{id} returns the building."""
    response = client.get(f"/api/v1/buildings/{building.id}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(building.id)
    assert response.json()["building_identifier"] == building.building_identifier


def test_get_building_not_found(client: TestClient) -> None:
    """An unknown building id returns 404."""
    response = client.get(f"/api/v1/buildings/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_list_buildings_for_parcel(client: TestClient, db_session: Session, parcel: Parcel) -> None:
    """GET /parcels/{id}/buildings lists only that parcel's buildings."""
    for index in range(2):
        factories.building_factory(db_session, parcel=parcel, building_identifier=f"OWN-{index}")
    other_parcel = factories.parcel_factory(db_session)
    factories.building_factory(db_session, parcel=other_parcel, building_identifier="OTHER-0")

    response = client.get(f"/api/v1/parcels/{parcel.id}/buildings")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert {item["building_identifier"] for item in body} == {"OWN-0", "OWN-1"}


def test_list_buildings_unknown_parcel(client: TestClient) -> None:
    """Listing under an unknown parcel returns 404."""
    response = client.get(f"/api/v1/parcels/{uuid.uuid4()}/buildings")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------


def test_update_building(client: TestClient, db_session: Session, building: Building) -> None:
    """PUT /buildings/{id} applies and stores the update."""
    response = client.put(
        f"/api/v1/buildings/{building.id}",
        json={"name": "Renamed", "construction_status": "under_construction"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed"

    db_session.expire_all()
    stored = db_session.get(Building, building.id)
    assert stored is not None
    assert stored.name == "Renamed"
    assert stored.construction_status is ConstructionStatus.UNDER_CONSTRUCTION


def test_update_building_not_found(client: TestClient) -> None:
    """Updating an unknown building returns 404."""
    response = client.put(f"/api/v1/buildings/{uuid.uuid4()}", json={"name": "Nope"})

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_update_building_rejects_invalid_status(client: TestClient, building: Building) -> None:
    """An unsupported construction_status is rejected."""
    response = client.put(
        f"/api/v1/buildings/{building.id}",
        json={"construction_status": "haunted"},
    )

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------------


def test_delete_building(client: TestClient, db_session: Session, building: Building) -> None:
    """DELETE /buildings/{id} returns 204 and removes the row."""
    building_id = building.id
    response = client.delete(f"/api/v1/buildings/{building_id}")

    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.get(Building, building_id) is None


def test_delete_building_not_found(client: TestClient) -> None:
    """Deleting an unknown building returns 404."""
    response = client.delete(f"/api/v1/buildings/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# Enum regression (the values_callable fix)
# --------------------------------------------------------------------------


def test_building_enums_round_trip_through_postgres(
    client: TestClient, db_session: Session, parcel: Parcel
) -> None:
    """Every building enum survives a real write/read cycle as its lowercase label.

    Regression guard for the ``values_callable`` fix: without it the ORM binds
    Python member names (``RESIDENTIAL``) and raises ``LookupError`` when reading
    back PostgreSQL's lowercase labels.
    """
    combinations = [
        (BuildingType.RESIDENTIAL, ConstructionStatus.PLANNED),
        (BuildingType.COMMERCIAL, ConstructionStatus.UNDER_CONSTRUCTION),
        (BuildingType.MIXED_USE, ConstructionStatus.DEMOLISHED),
        (BuildingType.INDUSTRIAL, ConstructionStatus.COMPLETED),
        (BuildingType.INSTITUTIONAL, ConstructionStatus.PLANNED),
    ]

    for building_type, construction_status in combinations:
        response = client.post(
            f"/api/v1/parcels/{parcel.id}/buildings",
            json=_payload(
                building_identifier=f"ENUM-{building_type.value}-{construction_status.value}",
                building_type=building_type.value,
                construction_status=construction_status.value,
            ),
        )
        assert response.status_code == 201, response.text
        building_id = response.json()["id"]

        db_session.expire_all()
        stored = db_session.get(Building, building_id)
        assert stored is not None
        assert stored.building_type is building_type
        assert stored.construction_status is construction_status

        # And through the API, which is where the LookupError previously surfaced.
        read = client.get(f"/api/v1/buildings/{building_id}")
        assert read.status_code == 200, read.text
        assert read.json()["building_type"] == building_type.value
        assert read.json()["construction_status"] == construction_status.value

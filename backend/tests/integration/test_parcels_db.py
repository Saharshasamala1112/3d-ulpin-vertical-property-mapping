"""Parcel CRUD against a real PostGIS database.

Also the regression test for the WKB fix: the service reads geometry back out of
PostgreSQL as a ``WKBElement`` and must convert ``element.data`` (the EWKB
payload) rather than the element itself, which raises
``TypeError: cannot convert 'WKBElement' object to bytes``.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKBElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.parcel import ULPIN, Parcel, ParcelStatus
from tests.integration import factories

pytestmark = pytest.mark.integration

BASE = "/api/v1/parcels"

MULTIPOLYGON = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.50, 12.90],
                [77.60, 12.90],
                [77.60, 13.00],
                [77.50, 13.00],
                [77.50, 12.90],
            ]
        ]
    ],
}


def _payload(**overrides) -> dict:
    payload = {
        "parcel_identifier": "PAREL-TEST-0001",
        "ulpin": "ULPIN-TEST-0001",
        "geometry": MULTIPOLYGON,
        "area_sqm": 1500.0,
        "status": "active",
        "metadata": {"source": "integration-test"},
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------


def test_create_parcel_persists_geometry(client: TestClient, db_session: Session) -> None:
    """POST /parcels returns 201 and the row is really stored."""
    response = client.post(BASE, json=_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["properties"]["parcel_identifier"] == "PAREL-TEST-0001"
    assert body["properties"]["ulpin"] == "ULPIN-TEST-0001"
    assert body["geometry"]["type"] == "MultiPolygon"

    stored = db_session.get(Parcel, body["id"])
    assert stored is not None
    assert stored.area_sqm == 1500.0
    assert stored.status.value == "active"


def test_create_parcel_rejects_duplicate_ulpin(client: TestClient, db_session: Session) -> None:
    """A duplicate ulpin returns 409 with the standard error contract."""
    factories.parcel_factory(db_session, ulpin="ULPIN-DUPLICATE")

    response = client.post(BASE, json=_payload(ulpin="ULPIN-DUPLICATE"))

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error_code"] == "DUPLICATE_PARCEL"
    assert "already exists" in body["message"]
    assert body["details"] == {}


def test_create_parcel_rejects_duplicate_identifier(
    client: TestClient, db_session: Session
) -> None:
    """A duplicate parcel_identifier is rejected the same way."""
    factories.parcel_factory(db_session, parcel_identifier="PAREL-DUPLICATE")

    response = client.post(BASE, json=_payload(parcel_identifier="PAREL-DUPLICATE"))

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "DUPLICATE_PARCEL"


def test_create_parcel_validates_body(client: TestClient) -> None:
    """An invalid body returns 422 VALIDATION_ERROR with per-field details."""
    response = client.post(BASE, json=_payload(area_sqm=-1))

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"
    assert "area_sqm" in body["details"]


# --------------------------------------------------------------------------
# READ
# --------------------------------------------------------------------------


def test_get_parcel_returns_geojson_feature(client: TestClient, parcel: Parcel) -> None:
    """GET /parcels/{id} returns a GeoJSON Feature wrapper."""
    response = client.get(f"{BASE}/{parcel.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "Feature"
    assert body["id"] == str(parcel.id)
    assert body["properties"]["ulpin"] == parcel.ulpin


def test_get_parcel_not_found(client: TestClient) -> None:
    """An unknown id returns 404 with the standard error contract."""
    response = client.get(f"{BASE}/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert body["message"]
    assert isinstance(body["details"], dict)


def test_list_parcels_paginates(client: TestClient, db_session: Session) -> None:
    """GET /parcels returns features plus pagination metadata."""
    for index in range(3):
        factories.parcel_factory(db_session, parcel_identifier=f"LISTED-{index}")

    response = client.get(BASE, params={"page": 1, "per_page": 2})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["page"] == 1
    assert body["meta"]["per_page"] == 2
    assert body["meta"]["total"] >= 3
    assert body["meta"]["total_pages"] >= 2


def test_list_parcels_rejects_invalid_pagination(client: TestClient) -> None:
    """per_page above the documented maximum is rejected."""
    response = client.get(BASE, params={"per_page": 500})

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------


def test_update_parcel_persists_changes(
    client: TestClient, db_session: Session, parcel: Parcel
) -> None:
    """PUT /parcels/{id} applies and stores the update."""
    response = client.put(
        f"{BASE}/{parcel.id}",
        json={"area_sqm": 2500.0, "status": "registered"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["properties"]["area_sqm"] == 2500.0
    assert response.json()["properties"]["status"] == "registered"

    db_session.expire_all()
    stored = db_session.get(Parcel, parcel.id)
    assert stored is not None
    assert stored.area_sqm == 2500.0
    assert stored.status.value == "registered"


def test_update_parcel_not_found(client: TestClient) -> None:
    """Updating an unknown parcel returns 404."""
    response = client.put(f"{BASE}/{uuid.uuid4()}", json={"area_sqm": 10.0})

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_update_parcel_rejects_conflicting_identifier(
    client: TestClient, db_session: Session, parcel: Parcel
) -> None:
    """Moving a parcel onto another parcel's identifier returns 409."""
    other = factories.parcel_factory(db_session)

    response = client.put(f"{BASE}/{parcel.id}", json={"ulpin": other.ulpin})

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "DUPLICATE_PARCEL"


# --------------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------------


def test_delete_parcel_soft_deletes_by_archiving(
    client: TestClient, db_session: Session, parcel: Parcel
) -> None:
    """DELETE /parcels/{id} returns 204 and archives the row (soft delete)."""
    parcel_id = parcel.id
    response = client.delete(f"{BASE}/{parcel_id}")

    assert response.status_code == 204, response.text
    db_session.expire_all()
    stored = db_session.get(Parcel, parcel_id)
    assert stored is not None, "parcels are soft-deleted, the row must still exist"
    assert stored.status is ParcelStatus.ARCHIVED


def test_delete_parcel_not_found(client: TestClient) -> None:
    """Deleting an unknown parcel returns 404."""
    response = client.delete(f"{BASE}/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# ULPIN
# --------------------------------------------------------------------------


def test_get_ulpin_returns_record(client: TestClient, db_session: Session) -> None:
    """GET /parcels/{id}/ulpin returns the issued ULPIN."""
    parcel = factories.parcel_factory(db_session)
    factories.ulpin_factory(db_session, parcel=parcel)

    response = client.get(f"{BASE}/{parcel.id}/ulpin")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parcel_id"] == str(parcel.id)
    assert body["issuing_authority"] == "Test Authority"
    assert len(body["checksum"]) == 64


def test_get_ulpin_missing_record(client: TestClient, db_session: Session) -> None:
    """A parcel with no ULPIN row returns 404."""
    parcel = factories.parcel_factory(db_session)
    assert (
        db_session.execute(
            select(ULPIN.id).where(ULPIN.parcel_id == parcel.id)
        ).scalar_one_or_none()
        is None
    )

    response = client.get(f"{BASE}/{parcel.id}/ulpin")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


def test_get_ulpin_unknown_parcel(client: TestClient) -> None:
    """Requesting a ULPIN for an unknown parcel returns 404."""
    response = client.get(f"{BASE}/{uuid.uuid4()}/ulpin")

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# Geometry regression (the WKB fix)
# --------------------------------------------------------------------------


def test_geometry_read_back_from_postgis_converts_correctly(
    client: TestClient, db_session: Session
) -> None:
    """A geometry loaded from PostGIS is a WKBElement and must survive a GET.

    Regression guard for the WKB fix: converting the element object instead of
    ``element.data`` raised ``TypeError: cannot convert 'WKBElement' object to
    bytes`` and turned every GET after a write into a 500.
    """
    created = client.post(BASE, json=_payload(parcel_identifier="GEOM-REGRESSION"))
    assert created.status_code == 201, created.text
    parcel_id = created.json()["id"]

    db_session.expire_all()
    stored = db_session.get(Parcel, parcel_id)
    assert stored is not None
    assert isinstance(stored.geometry, WKBElement), "expected PostGIS to return a WKBElement"

    # The element exposes its payload via .data, and that is what the service uses.
    assert isinstance(stored.geometry.data, bytes)

    response = client.get(f"{BASE}/{parcel_id}")
    assert response.status_code == 200, response.text
    assert response.json()["geometry"]["type"] == "MultiPolygon"


def test_geometry_survives_update_cycle(client: TestClient, parcel: Parcel) -> None:
    """Reading a geometry after a write-back is stable across endpoints."""
    assert client.get(f"{BASE}/{parcel.id}").status_code == 200
    assert client.put(f"{BASE}/{parcel.id}", json={"area_sqm": 1234.5}).status_code == 200
    assert client.get(f"{BASE}/{parcel.id}").status_code == 200

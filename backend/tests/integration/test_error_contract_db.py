"""The standardized error contract and health endpoints, against a real database.

Every error response the API produces must be
``{"error_code": str, "message": str, "details": dict}``.

Note the deliberate exception that already exists in ``app.main``: ``401`` /
``403`` responses from the authentication routes keep the legacy
``{"detail": ...}`` body, which is asserted explicitly below so the exception
stays intentional rather than accidental.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.floor import Floor
from app.models.parcel import Parcel
from app.models.unit import Unit
from tests.integration import factories

pytestmark = pytest.mark.integration

ERROR_KEYS = {"error_code", "message", "details"}


def _assert_standard_error(response, status_code: int, error_code: str | None = None) -> dict:
    """Assert the response uses the standard error envelope and return its body."""
    assert response.status_code == status_code, response.text
    body = response.json()
    assert isinstance(body, dict), body
    assert set(body) == ERROR_KEYS, f"unexpected error shape: {body}"
    assert isinstance(body["error_code"], str) and body["error_code"]
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["details"], dict)
    if error_code is not None:
        assert body["error_code"] == error_code
    return body


# --------------------------------------------------------------------------
# 404 NOT_FOUND
# --------------------------------------------------------------------------


def test_not_found_uses_standard_contract(client: TestClient) -> None:
    """An unknown parcel id returns the standard NOT_FOUND envelope."""
    response = client.get(f"/api/v1/parcels/{uuid.uuid4()}")

    body = _assert_standard_error(response, 404, "NOT_FOUND")
    assert body["details"] == {}


def test_not_found_message_is_human_readable(client: TestClient) -> None:
    """The 404 handler supplies a default message rather than leaking a dict."""
    response = client.get(f"/api/v1/buildings/{uuid.uuid4()}")

    body = _assert_standard_error(response, 404, "NOT_FOUND")
    assert isinstance(body["message"], str)
    assert "{" not in body["message"], body["message"]


# --------------------------------------------------------------------------
# 409 CONFLICT
# --------------------------------------------------------------------------


def test_conflict_uses_standard_contract(client: TestClient, db_session: Session) -> None:
    """A duplicate parcel returns the standard CONFLICT envelope."""
    factories.parcel_factory(db_session, ulpin="ULPIN-CONFLICT-CONTRACT")

    response = client.post(
        "/api/v1/parcels",
        json={
            "parcel_identifier": "PARCEL-CONTRACT",
            "ulpin": "ULPIN-CONFLICT-CONTRACT",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]]
                ],
            },
            "area_sqm": 100.0,
            "status": "draft",
        },
    )

    _assert_standard_error(response, 409, "DUPLICATE_PARCEL")


# --------------------------------------------------------------------------
# 422 VALIDATION_ERROR
# --------------------------------------------------------------------------


def test_validation_error_uses_standard_contract_with_details(
    client: TestClient,
) -> None:
    """Validation failures report per-field messages in ``details``."""
    response = client.post("/api/v1/parcels", json={"parcel_identifier": "only-this"})

    body = _assert_standard_error(response, 422, "VALIDATION_ERROR")
    assert body["message"] == "Request validation failed"
    assert set(body["details"]) >= {"ulpin", "geometry", "area_sqm"}
    assert all(isinstance(value, str) for value in body["details"].values())


def test_validation_error_for_query_parameters(client: TestClient) -> None:
    """Query-parameter validation failures use the same envelope."""
    response = client.get("/api/v1/parcels", params={"page": 0})

    body = _assert_standard_error(response, 422, "VALIDATION_ERROR")
    assert "page" in body["details"]


def test_service_validation_error_uses_standard_contract(
    client: TestClient, parcel: Parcel
) -> None:
    """A service-level geometry rejection also uses the standard envelope."""
    response = client.post(
        f"/api/v1/parcels/{parcel.id}/buildings",
        json={
            "building_identifier": "BLDG-BAD-GEOM",
            "building_type": "residential",
            "construction_status": "planned",
            "footprint_geometry": {"type": "Point", "coordinates": [77.5, 12.9]},
        },
    )

    _assert_standard_error(response, 422, "VALIDATION_ERROR")


# --------------------------------------------------------------------------
# 500 INTERNAL_ERROR
# --------------------------------------------------------------------------


def test_unhandled_exception_uses_standard_contract(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database failure returns the standard 500 envelope, not a traceback.

    The failure is induced by making every query raise, which exercises the
    application's own ``Exception`` handler. The point is the response shape,
    which must never leak internal detail to the client.
    """

    def _explode(*args, **kwargs):
        raise RuntimeError("synthetic database failure")

    monkeypatch.setattr(Session, "query", _explode)

    response = client.get("/api/v1/parcels")

    body = _assert_standard_error(response, 500, "INTERNAL_ERROR")
    assert body["message"] == "Internal server error"
    assert "synthetic" not in response.text
    assert response.headers["X-Request-ID"]


# --------------------------------------------------------------------------
# Request metadata
# --------------------------------------------------------------------------


def test_every_response_carries_request_id(client: TestClient, parcel: Parcel) -> None:
    """Success and error responses alike carry the request correlation header."""
    ok = client.get(f"/api/v1/parcels/{parcel.id}")
    assert ok.status_code == 200
    assert ok.headers["X-Request-ID"]
    assert ok.headers["X-Response-Time"].endswith("ms")

    missing = client.get(f"/api/v1/parcels/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.headers["X-Request-ID"]


# --------------------------------------------------------------------------
# Documented legacy exception
# --------------------------------------------------------------------------


def test_auth_401_keeps_legacy_detail_body(client: TestClient) -> None:
    """Auth failures intentionally keep the legacy ``{"detail": ...}`` body.

    ``app.main`` documents this exception: 401/403 responses from the auth
    routes are not wrapped in the standard envelope.
    """
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401, response.text
    body = response.json()
    assert set(body) == {"detail"}, body
    assert isinstance(body["detail"], dict)
    assert body["detail"]["error"]["code"] == "AUTHENTICATION_FAILED"


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/health"])
def test_health_endpoints_report_ok(client: TestClient, path: str) -> None:
    """Both health routes are reachable and report a healthy service."""
    response = client.get(path)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"


def test_legacy_health_endpoint_reports_service_name(client: TestClient) -> None:
    """The pre-existing /api/health route is preserved."""
    response = client.get("/api/health")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "service": "geosix-api"}


def test_root_metadata_endpoint(client: TestClient) -> None:
    """The API root reports service, version, and docs locations."""
    response = client.get("/api/v1")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["service"]
    assert body["version"]
    assert body["docs"] == "/docs"


def test_test_database_is_migrated_postgis(healthy_database: None) -> None:
    """Guard that these tests ran against a real migrated PostGIS database."""
    assert healthy_database is None


# --------------------------------------------------------------------------
# Cascade behaviour across the hierarchy
# --------------------------------------------------------------------------


def test_deleting_a_building_removes_its_floors_and_units(
    client: TestClient, db_session: Session, building: Building
) -> None:
    """Deleting a building cascades to floors and units in PostgreSQL."""
    floor = factories.floor_factory(db_session, building=building)
    unit = factories.unit_factory(db_session, floor=floor)
    floor_id, unit_id = floor.id, unit.id

    assert client.delete(f"/api/v1/buildings/{building.id}").status_code == 204

    db_session.expire_all()
    assert db_session.get(Building, building.id) is None
    assert db_session.get(Floor, floor_id) is None
    assert db_session.get(Unit, unit_id) is None


def test_deleting_a_floor_removes_its_units(
    client: TestClient, db_session: Session, floor: Floor
) -> None:
    """Deleting a floor cascades to its units."""
    unit = factories.unit_factory(db_session, floor=floor)
    unit_id, floor_id = unit.id, floor.id

    assert client.delete(f"/api/v1/floors/{floor_id}").status_code == 204

    db_session.expire_all()
    assert db_session.get(Floor, floor_id) is None
    assert db_session.get(Unit, unit_id) is None

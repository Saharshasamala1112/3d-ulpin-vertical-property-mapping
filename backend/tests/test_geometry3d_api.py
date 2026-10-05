from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.geometry3d import GeometryType
from app.schemas.geometry3d import Geometry3DResponse
from tests.auth_support import bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))

_VALID_BODY = {
    "x_min": "1.123456",
    "x_max": "5.654321",
    "y_min": "2.5",
    "y_max": "7.25",
    "z_min": "0.1",
    "z_max": "3.141593",
    "geometry_type": "aabb",
}


def _response(unit_id):
    return Geometry3DResponse(
        id=uuid4(),
        unit_id=unit_id,
        x_min=Decimal("1.123456"),
        x_max=Decimal("5.654321"),
        y_min=Decimal("2.5"),
        y_max=Decimal("7.25"),
        z_min=Decimal("0.1"),
        z_max=Decimal("3.141593"),
        geometry_type=GeometryType.AABB,
        created_at="2026-09-29T00:00:00Z",
        updated_at="2026-09-29T00:00:00Z",
        volume=Decimal("65.388"),
        centroid=(Decimal("3.3888885"), Decimal("4.875"), Decimal("1.6207965")),
        dimensions=(Decimal("4.530865"), Decimal("4.75"), Decimal("3.041593")),
    )


def test_geometry_routes_are_in_openapi():
    paths = app.openapi()["paths"]

    assert "/api/v1/units/{unit_id}/geometry" in paths
    assert set(paths["/api/v1/units/{unit_id}/geometry"]) == {"get", "put"}


def test_geometry_get_matches_unit_endpoint_auth_behavior():
    unit_id = uuid4()
    with patch("app.api.v1.geometry.get_geometry_by_unit", return_value=_response(unit_id)):
        response = client.get(f"/api/v1/units/{unit_id}/geometry")

    assert response.status_code == 200


def test_geometry_put_rejects_equal_bounds_with_validation_error():
    body = _VALID_BODY | {"x_min": "1.0", "x_max": "1.0"}

    response = client.put(f"/api/v1/units/{uuid4()}/geometry", json=body)

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "x_max" in response.json()["details"]


def test_geometry_put_rejects_unsupported_type():
    body = _VALID_BODY | {"geometry_type": "mesh"}

    response = client.put(f"/api/v1/units/{uuid4()}/geometry", json=body)

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "geometry_type" in response.json()["details"]

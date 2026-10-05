from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.geometry3d import PropertyGeometry
from app.models.unit import Unit
from tests.integration import factories

pytestmark = pytest.mark.integration

_GEOMETRY_BODY = {
    "x_min": "1.123456",
    "x_max": "5.654321",
    "y_min": "2.5",
    "y_max": "7.25",
    "z_min": "0.1",
    "z_max": "3.141593",
    "geometry_type": "aabb",
}


def test_get_geometry_returns_persisted_fields_and_computed_measurements(
    client: TestClient, db_session: Session, unit: Unit
) -> None:
    geometry = factories.property_geometry_factory(
        db_session,
        unit,
        x_min=Decimal("1.123456"),
        x_max=Decimal("5.654321"),
        y_min=Decimal("2.5"),
        y_max=Decimal("7.25"),
        z_min=Decimal("0.1"),
        z_max=Decimal("3.141593"),
    )

    response = client.get(f"/api/v1/units/{unit.id}/geometry")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(geometry.id)
    assert body["unit_id"] == str(unit.id)
    assert body["geometry_type"] == "aabb"
    assert body["x_min"] == "1.123456"

    x_width = Decimal("5.654321") - Decimal("1.123456")
    y_width = Decimal("7.25") - Decimal("2.5")
    z_width = Decimal("3.141593") - Decimal("0.1")
    assert Decimal(body["volume"]) == x_width * y_width * z_width
    assert tuple(map(Decimal, body["centroid"])) == (
        (Decimal("1.123456") + Decimal("5.654321")) / Decimal("2"),
        (Decimal("2.5") + Decimal("7.25")) / Decimal("2"),
        (Decimal("0.1") + Decimal("3.141593")) / Decimal("2"),
    )
    assert tuple(map(Decimal, body["dimensions"])) == (x_width, y_width, z_width)


def test_get_geometry_missing_unit_returns_standard_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/units/{uuid4()}/geometry")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_get_geometry_missing_geometry_returns_standard_404(
    client: TestClient, db_session: Session, floor
) -> None:
    unit = factories.unit_factory(db_session, floor=floor, geometry=False)
    response = client.get(f"/api/v1/units/{unit.id}/geometry")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_put_geometry_creates_then_replaces_exactly_one_row(
    client: TestClient, db_session: Session, unit: Unit
) -> None:
    first = client.put(f"/api/v1/units/{unit.id}/geometry", json=_GEOMETRY_BODY)

    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    replacement = _GEOMETRY_BODY | {
        "x_min": "-2.000001",
        "x_max": "8.000009",
        "geometry_type": "polygon_3d",
    }
    second = client.put(f"/api/v1/units/{unit.id}/geometry", json=replacement)

    assert second.status_code == 200, second.text
    assert second.json()["id"] == first_id
    assert second.json()["x_min"] == "-2.000001"
    assert second.json()["x_max"] == "8.000009"
    db_session.expire_all()
    assert (
        db_session.query(func.count(PropertyGeometry.id))
        .filter(PropertyGeometry.unit_id == unit.id)
        .scalar()
        == 1
    )

    stored = db_session.query(PropertyGeometry).filter_by(unit_id=unit.id).one()
    assert stored.x_min == Decimal("-2.000001")
    assert stored.x_max == Decimal("8.000009")
    assert stored.geometry_type.value == "polygon_3d"


def test_put_geometry_unknown_unit_returns_404(client: TestClient) -> None:
    response = client.put(f"/api/v1/units/{uuid4()}/geometry", json=_GEOMETRY_BODY)

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("x_max", "1.123456"),
        ("x_max", "1.0"),
        ("y_max", "2.5"),
        ("y_max", "2.0"),
        ("z_max", "0.1"),
        ("z_max", "0.0"),
    ],
)
def test_put_geometry_rejects_non_increasing_bounds(
    client: TestClient, unit: Unit, field: str, invalid_value: str
) -> None:
    response = client.put(
        f"/api/v1/units/{unit.id}/geometry",
        json=_GEOMETRY_BODY | {field: invalid_value},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert field in response.json()["details"]


def test_put_geometry_rejects_unsupported_type(client: TestClient, unit: Unit) -> None:
    response = client.put(
        f"/api/v1/units/{unit.id}/geometry",
        json=_GEOMETRY_BODY | {"geometry_type": "mesh"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "geometry_type" in response.json()["details"]


def test_unit_deletion_cascades_geometry_and_subsequent_get_is_404(
    client: TestClient, db_session: Session, unit: Unit
) -> None:
    geometry = factories.property_geometry_factory(db_session, unit)
    geometry_id = geometry.id
    unit_id = unit.id
    db_session.commit()

    db_session.delete(unit)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(PropertyGeometry, geometry_id) is None
    response = client.get(f"/api/v1/units/{unit_id}/geometry")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"

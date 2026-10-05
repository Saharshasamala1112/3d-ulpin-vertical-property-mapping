from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.unit import Unit, UnitStatus, UnitType
from app.models.user import User, UserRole
from app.schemas.unit import UnitResponse, UnitVDCResponse
from tests.auth_support import ADMIN_ID, SEED_EMAILS, bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))


def _unit_response(floor_id: str | None = None) -> UnitResponse:
    return UnitResponse(
        id=str(uuid4()),
        floor_id=str(floor_id or uuid4()),
        unit_identifier="UNIT-101",
        unit_type="residential",
        area_sqm=55.5,
        x_min=0.0,
        x_max=5.0,
        y_min=0.0,
        y_max=4.5,
        z_min=0.0,
        z_max=3.0,
        status="planned",
        vdc_code=None,
        created_at="2026-09-20T00:00:00+00:00",
        updated_at="2026-09-20T00:00:00+00:00",
    )


VALID_UNIT_PAYLOAD = {
    "unit_identifier": "UNIT-101",
    "unit_type": "residential",
    "area_sqm": 55.5,
    "x_min": 0.0,
    "x_max": 5.0,
    "y_min": 0.0,
    "y_max": 4.5,
    "z_min": 0.0,
    "z_max": 3.0,
}


class _FakeUnitQuery:
    def __init__(self, unit: Unit):
        self.unit = unit

    def filter(self, *_args):
        return self

    def with_for_update(self, **_kwargs):
        return self

    def options(self, *_args):
        return self

    def first(self):
        return self.unit


class _FakeUnitSession:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.unit = Unit(
            id=uuid4(),
            floor_id=uuid4(),
            unit_identifier="UNIT-101",
            unit_type=UnitType.RESIDENTIAL,
            area_sqm=55.5,
            status=UnitStatus.PLANNED,
            created_at=now,
            updated_at=now,
        )
        self.unit.geometry = PropertyGeometry(
            id=uuid4(),
            unit_id=self.unit.id,
            x_min=0,
            x_max=5,
            y_min=0,
            y_max=4.5,
            z_min=0,
            z_max=3,
            geometry_type=GeometryType.AABB,
            created_at=now,
            updated_at=now,
        )
        self.commit_count = 0
        #: ``get_current_user`` stamps the acting user id on ``session.info``.
        self.info: dict = {}
        #: Minimal active admin user returned by ``db.get(User, ...)`` so the
        #: bearer token resolves; every other lookup misses.
        self.admin_user = User(
            id=ADMIN_ID,
            email=SEED_EMAILS["admin"],
            password_hash="",
            full_name="Admin Tester",
            is_active=True,
            role=UserRole.ADMIN,
            created_at=now,
            updated_at=now,
        )

    def query(self, *_args):
        return _FakeUnitQuery(self.unit)

    def get(self, model, pk, **_kwargs):
        if model is User and pk == ADMIN_ID:
            return self.admin_user
        return None

    def commit(self):
        self.commit_count += 1

    def refresh(self, _unit):
        pass


@pytest.fixture
def persisted_unit_client():
    session = _FakeUnitSession()

    def override_get_db():
        yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    # Deliberately not a context manager: entering TestClient would fire
    # app lifespan, which probes the real database engine.
    test_client = TestClient(app, headers=bearer_headers("admin"))
    try:
        yield test_client, session
    finally:
        test_client.close()
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


class TestCreateUnit:
    @patch("app.api.v1.units.create_unit")
    def test_create_unit_success(self, mock_create):
        floor_id = uuid4()
        unit = _unit_response(str(floor_id))
        mock_create.return_value = unit
        response = client.post(f"/api/v1/floors/{floor_id}/units", json=VALID_UNIT_PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        assert data["floor_id"] == str(floor_id)
        assert data["unit_identifier"] == "UNIT-101"
        assert data["unit_type"] == "residential"

    @patch("app.api.v1.units.create_unit")
    def test_create_unit_floor_not_found(self, mock_create):
        mock_create.side_effect = ValueError("Floor not found")
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=VALID_UNIT_PAYLOAD)
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"

    def test_create_unit_invalid_unit_type(self):
        payload = {**VALID_UNIT_PAYLOAD, "unit_type": "industrial"}
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=payload)
        assert response.status_code == 422

    def test_create_unit_equal_bounds_rejected(self):
        payload = {**VALID_UNIT_PAYLOAD, "x_min": 5.0}
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=payload)
        assert response.status_code == 422

    def test_create_unit_missing_required_fields(self):
        response = client.post(
            f"/api/v1/floors/{uuid4()}/units",
            json={"unit_identifier": "UNIT-101"},
        )
        assert response.status_code == 422

    def test_create_unit_negative_area(self):
        payload = {**VALID_UNIT_PAYLOAD, "area_sqm": -10}
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=payload)
        assert response.status_code == 422

    def test_create_unit_x_min_greater_than_x_max(self):
        payload = {**VALID_UNIT_PAYLOAD, "x_min": 6.0, "x_max": 5.0}
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=payload)
        assert response.status_code == 422

    def test_create_unit_z_min_greater_than_z_max(self):
        payload = {**VALID_UNIT_PAYLOAD, "z_min": 4.0, "z_max": 3.0}
        response = client.post(f"/api/v1/floors/{uuid4()}/units", json=payload)
        assert response.status_code == 422


class TestListUnits:
    @patch("app.api.v1.units.list_units")
    def test_list_units_success(self, mock_list):
        floor_id = uuid4()
        mock_list.return_value = [_unit_response(str(floor_id))]
        response = client.get(f"/api/v1/floors/{floor_id}/units")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["unit_identifier"] == "UNIT-101"

    @patch("app.api.v1.units.list_units")
    def test_list_units_floor_not_found(self, mock_list):
        mock_list.side_effect = ValueError("Floor not found")
        response = client.get(f"/api/v1/floors/{uuid4()}/units")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"


class TestGetUnit:
    @patch("app.api.v1.units.get_unit")
    def test_get_unit_success(self, mock_get):
        unit = _unit_response()
        mock_get.return_value = unit
        response = client.get(f"/api/v1/units/{uuid4()}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == unit.id
        assert data["unit_type"] == "residential"

    @patch("app.api.v1.units.get_unit")
    def test_get_unit_not_found(self, mock_get):
        mock_get.side_effect = ValueError("Unit not found")
        response = client.get(f"/api/v1/units/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"


class TestUpdateUnit:
    @patch("app.api.v1.units.update_unit")
    def test_update_unit_success(self, mock_update):
        unit = _unit_response()
        mock_update.return_value = unit
        response = client.put(
            f"/api/v1/units/{uuid4()}",
            json={"status": "active", "area_sqm": 60.0},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "planned"

    @patch("app.api.v1.units.update_unit")
    def test_update_unit_not_found(self, mock_update):
        mock_update.side_effect = ValueError("Unit not found")
        response = client.put(
            f"/api/v1/units/{uuid4()}",
            json={"status": "active"},
        )
        assert response.status_code == 404

    def test_update_unit_invalid_status(self):
        response = client.put(
            f"/api/v1/units/{uuid4()}",
            json={"status": "foreclosed"},
        )
        assert response.status_code == 422

    def test_update_unit_inverted_bbox_rejected(self):
        response = client.put(
            f"/api/v1/units/{uuid4()}",
            json={"x_min": 7.0, "x_max": 3.0},
        )
        assert response.status_code == 422

    def test_update_unit_equal_bounds_rejected(self, persisted_unit_client):
        test_client, session = persisted_unit_client
        response = test_client.put(
            f"/api/v1/units/{session.unit.id}",
            json={"x_min": 5.0},
        )
        assert response.status_code == 422
        assert session.commit_count == 0

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("x_min", 7.0),
            ("x_max", -1.0),
            ("y_min", 5.0),
            ("y_max", -1.0),
            ("z_min", 4.0),
            ("z_max", -1.0),
        ],
    )
    def test_update_unit_partial_bbox_rejected(self, persisted_unit_client, field, value):
        test_client, session = persisted_unit_client

        response = test_client.put(f"/api/v1/units/{session.unit.id}", json={field: value})

        assert response.status_code == 422
        assert session.commit_count == 0

    def test_update_unit_valid_partial_bbox_update(self, persisted_unit_client):
        test_client, session = persisted_unit_client

        response = test_client.put(
            f"/api/v1/units/{session.unit.id}",
            json={"x_max": 8.0},
        )

        assert response.status_code == 200
        assert response.json()["x_max"] == 8.0
        assert session.unit.geometry.x_max == 8.0
        assert session.commit_count == 1


class TestDeleteUnit:
    @patch("app.api.v1.units.delete_unit")
    def test_delete_unit_success(self, mock_delete):
        response = client.delete(f"/api/v1/units/{uuid4()}")
        assert response.status_code == 204

    @patch("app.api.v1.units.delete_unit")
    def test_delete_unit_not_found(self, mock_delete):
        mock_delete.side_effect = ValueError("Unit not found")
        response = client.delete(f"/api/v1/units/{uuid4()}")
        assert response.status_code == 404


class TestGetUnitVDC:
    @patch("app.api.v1.units.get_unit_vdc")
    def test_get_vdc_success_with_code(self, mock_get_vdc):
        unit_id = uuid4()
        mock_get_vdc.return_value = UnitVDCResponse(
            unit_id=str(unit_id),
            vdc_code="GEOSX12345-A-F1-U101-A1B2",
        )
        response = client.get(f"/api/v1/units/{unit_id}/vdc")
        assert response.status_code == 200
        data = response.json()
        assert data["unit_id"] == str(unit_id)
        assert data["vdc_code"] == "GEOSX12345-A-F1-U101-A1B2"

    @patch("app.api.v1.units.get_unit_vdc")
    def test_get_vdc_returns_parsed_segments(self, mock_get_vdc):
        unit_id = uuid4()
        mock_get_vdc.return_value = UnitVDCResponse(
            unit_id=str(unit_id),
            vdc_code="GEOSX12345-B-F2-U205-9F3E",
            ulpin="GEOSX12345",
            domain="B",
            level="F2",
            unit="U205",
            checksum="9F3E",
        )
        response = client.get(f"/api/v1/units/{unit_id}/vdc")
        assert response.status_code == 200
        data = response.json()
        assert data["ulpin"] == "GEOSX12345"
        assert data["domain"] == "B"
        assert data["level"] == "F2"
        assert data["unit"] == "U205"
        assert data["checksum"] == "9F3E"

    @patch("app.api.v1.units.get_unit_vdc")
    def test_get_vdc_success_null_code(self, mock_get_vdc):
        unit_id = uuid4()
        mock_get_vdc.return_value = UnitVDCResponse(unit_id=str(unit_id), vdc_code=None)
        response = client.get(f"/api/v1/units/{unit_id}/vdc")
        assert response.status_code == 200
        data = response.json()
        assert data["vdc_code"] is None
        for segment in ("ulpin", "domain", "level", "unit", "checksum"):
            assert data[segment] is None, f"{segment} should be null when no code is stored"

    @patch("app.api.v1.units.get_unit_vdc")
    def test_get_vdc_unparseable_code_keeps_code_null_segments(self, mock_get_vdc):
        """A stored code the parser rejects is still returned, with null segments."""
        unit_id = uuid4()
        mock_get_vdc.return_value = UnitVDCResponse(
            unit_id=str(unit_id),
            vdc_code="VDC-0000-0001",
        )
        response = client.get(f"/api/v1/units/{unit_id}/vdc")
        assert response.status_code == 200
        data = response.json()
        assert data["vdc_code"] == "VDC-0000-0001"
        assert data["ulpin"] is None
        assert data["checksum"] is None

    @patch("app.api.v1.units.get_unit_vdc")
    def test_get_vdc_unit_not_found(self, mock_get_vdc):
        mock_get_vdc.side_effect = ValueError("Unit not found")
        response = client.get(f"/api/v1/units/{uuid4()}/vdc")
        assert response.status_code == 404


class TestGenerateUnitVDC:
    @patch("app.api.v1.units.generate_unit_vdc")
    def test_generate_vdc_returns_persisted_code(self, mock_generate):
        unit_id = uuid4()
        mock_generate.return_value = UnitVDCResponse(
            unit_id=str(unit_id),
            vdc_code="GEOSX12345-A-F1-U101-A1B2",
            status="present",
        )

        response = client.post(f"/api/v1/units/{unit_id}/vdc")

        assert response.status_code == 200
        assert response.json()["vdc_code"] == "GEOSX12345-A-F1-U101-A1B2"
        assert response.json()["status"] == "present"
        mock_generate.assert_called_once()

    @patch("app.api.v1.units.generate_unit_vdc")
    def test_generate_vdc_unencodable_hierarchy_is_422(self, mock_generate):
        from app.services.unit import VDCGenerationUnavailableError

        mock_generate.side_effect = VDCGenerationUnavailableError(
            "Unit hierarchy does not produce a valid VDC"
        )

        response = client.post(f"/api/v1/units/{uuid4()}/vdc")

        assert response.status_code == 422

    @patch("app.api.v1.units.generate_unit_vdc")
    def test_generate_vdc_unit_not_found_is_404(self, mock_generate):
        mock_generate.side_effect = ValueError("Unit not found")

        response = client.post(f"/api/v1/units/{uuid4()}/vdc")

        assert response.status_code == 404


class TestHierarchyNavigation:
    @patch("app.api.v1.units.list_units")
    def test_navigate_building_floor_units(self, mock_list_units):
        floor_id = uuid4()
        unit = _unit_response(str(floor_id))
        mock_list_units.return_value = [unit]
        response = client.get(f"/api/v1/floors/{floor_id}/units")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["floor_id"] == str(floor_id)
        assert data[0]["unit_identifier"] == "UNIT-101"
        mock_list_units.assert_called_once()


class TestOpenAPIDocumentation:
    def test_openapi_json_has_units_tag(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        tag_names = [t["name"] for t in response.json().get("tags", [])]
        assert "Units" in tag_names

    def test_openapi_json_has_units_paths(self):
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        assert "/api/v1/floors/{floor_id}/units" in paths
        assert "/api/v1/units/{unit_id}" in paths
        assert "/api/v1/units/{unit_id}/vdc" in paths

    def test_units_post_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        post_method = data["paths"]["/api/v1/floors/{floor_id}/units"].get("post", {})
        assert post_method.get("summary") == "Create a unit"
        assert "201" in post_method.get("responses", {})

    def test_units_get_list_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/floors/{floor_id}/units"].get("get", {})
        assert get_method.get("summary") == "List units of a floor"

    def test_units_get_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/units/{unit_id}"].get("get", {})
        assert get_method.get("summary") == "Get unit by ID"

    def test_units_put_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        put_method = data["paths"]["/api/v1/units/{unit_id}"].get("put", {})
        assert put_method.get("summary") == "Update a unit"

    def test_units_delete_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        delete_method = data["paths"]["/api/v1/units/{unit_id}"].get("delete", {})
        assert delete_method.get("summary") == "Delete a unit"

    def test_vdc_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        vdc_method = data["paths"]["/api/v1/units/{unit_id}/vdc"].get("get", {})
        assert vdc_method.get("summary") == "Get VDC code for a unit"

        post_method = data["paths"]["/api/v1/units/{unit_id}/vdc"].get("post", {})
        assert post_method.get("summary") == "Generate or refresh a unit VDC"

    def test_vdc_response_schema_exposes_parsed_segments(self):
        """W19: the VDC endpoint documents the five parsed segments."""
        response = client.get("/openapi.json")
        data = response.json()
        vdc_method = data["paths"]["/api/v1/units/{unit_id}/vdc"].get("get", {})
        schema_name = vdc_method["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].rsplit("/", 1)[-1]
        properties = data["components"]["schemas"][schema_name]["properties"]
        assert {
            "unit_id",
            "vdc_code",
            "status",
            "ulpin",
            "domain",
            "level",
            "unit",
            "checksum",
        } <= set(properties)

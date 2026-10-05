from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.floor import FloorResponse
from tests.auth_support import bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))


def _floor_response(building_id: str | None = None, floor_number: int = 1) -> FloorResponse:
    return FloorResponse(
        id=str(uuid4()),
        building_id=str(building_id or uuid4()),
        floor_number=floor_number,
        level_name="Ground Level",
        floor_type="ground",
        elevation_min=0.0,
        elevation_max=3.5,
        created_at="2026-09-20T00:00:00+00:00",
        updated_at="2026-09-20T00:00:00+00:00",
    )


class TestCreateFloor:
    @patch("app.api.v1.floors.create_floor")
    def test_create_floor_success(self, mock_create):
        building_id = uuid4()
        floor = _floor_response(str(building_id))
        mock_create.return_value = floor
        response = client.post(
            f"/api/v1/buildings/{building_id}/floors",
            json={
                "floor_number": 1,
                "level_name": "Ground Level",
                "floor_type": "ground",
                "elevation_min": 0.0,
                "elevation_max": 3.5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["building_id"] == str(building_id)
        assert data["floor_type"] == "ground"
        assert data["floor_number"] == 1

    @patch("app.api.v1.floors.create_floor")
    def test_create_floor_building_not_found(self, mock_create):
        mock_create.side_effect = ValueError("Building not found")
        response = client.post(
            f"/api/v1/buildings/{uuid4()}/floors",
            json={
                "floor_number": 1,
                "floor_type": "ground",
                "elevation_min": 0.0,
                "elevation_max": 3.5,
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"

    def test_create_floor_invalid_floor_type(self):
        response = client.post(
            f"/api/v1/buildings/{uuid4()}/floors",
            json={
                "floor_number": 1,
                "floor_type": "mezzanine",
                "elevation_min": 0.0,
                "elevation_max": 3.5,
            },
        )
        assert response.status_code == 422

    def test_create_floor_missing_required_fields(self):
        response = client.post(
            f"/api/v1/buildings/{uuid4()}/floors",
            json={"floor_type": "ground"},
        )
        assert response.status_code == 422


class TestListFloors:
    @patch("app.api.v1.floors.list_floors")
    def test_list_floors_success(self, mock_list):
        building_id = uuid4()
        mock_list.return_value = [_floor_response(str(building_id), floor_number=1)]
        response = client.get(f"/api/v1/buildings/{building_id}/floors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["floor_number"] == 1

    @patch("app.api.v1.floors.list_floors")
    def test_list_floors_building_not_found(self, mock_list):
        mock_list.side_effect = ValueError("Building not found")
        response = client.get(f"/api/v1/buildings/{uuid4()}/floors")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"

    @patch("app.api.v1.floors.list_floors")
    def test_list_floors_empty(self, mock_list):
        mock_list.return_value = []
        response = client.get(f"/api/v1/buildings/{uuid4()}/floors")
        assert response.status_code == 200
        assert response.json() == []


class TestGetFloor:
    @patch("app.api.v1.floors.get_floor")
    def test_get_floor_success(self, mock_get):
        floor = _floor_response()
        mock_get.return_value = floor
        response = client.get(f"/api/v1/floors/{uuid4()}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == floor.id
        assert data["level_name"] == "Ground Level"

    @patch("app.api.v1.floors.get_floor")
    def test_get_floor_not_found(self, mock_get):
        mock_get.side_effect = ValueError("Floor not found")
        response = client.get(f"/api/v1/floors/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"


class TestUpdateFloor:
    @patch("app.api.v1.floors.update_floor")
    def test_update_floor_success(self, mock_update):
        floor = _floor_response()
        mock_update.return_value = floor
        response = client.put(
            f"/api/v1/floors/{uuid4()}",
            json={"level_name": "Mezzanine", "elevation_max": 4.0},
        )
        assert response.status_code == 200
        assert response.json()["level_name"] == "Ground Level"

    @patch("app.api.v1.floors.update_floor")
    def test_update_floor_not_found(self, mock_update):
        mock_update.side_effect = ValueError("Floor not found")
        response = client.put(
            f"/api/v1/floors/{uuid4()}",
            json={"level_name": "Mezzanine"},
        )
        assert response.status_code == 404

    def test_update_floor_invalid_floor_type(self):
        response = client.put(
            f"/api/v1/floors/{uuid4()}",
            json={"floor_type": "attic"},
        )
        assert response.status_code == 422


class TestDeleteFloor:
    @patch("app.api.v1.floors.delete_floor")
    def test_delete_floor_success(self, mock_delete):
        response = client.delete(f"/api/v1/floors/{uuid4()}")
        assert response.status_code == 204

    @patch("app.api.v1.floors.delete_floor")
    def test_delete_floor_not_found(self, mock_delete):
        mock_delete.side_effect = ValueError("Floor not found")
        response = client.delete(f"/api/v1/floors/{uuid4()}")
        assert response.status_code == 404


class TestOpenAPIDocumentation:
    def test_openapi_json_has_floors_tag(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        tag_names = [t["name"] for t in response.json().get("tags", [])]
        assert "Floors" in tag_names

    def test_openapi_json_has_floors_paths(self):
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        assert "/api/v1/buildings/{building_id}/floors" in paths
        assert "/api/v1/floors/{floor_id}" in paths

    def test_floors_post_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        post_method = data["paths"]["/api/v1/buildings/{building_id}/floors"].get("post", {})
        assert post_method.get("summary") == "Create a floor"
        assert "201" in post_method.get("responses", {})

    def test_floors_get_list_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/buildings/{building_id}/floors"].get("get", {})
        assert get_method.get("summary") == "List floors of a building"

    def test_floors_get_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/floors/{floor_id}"].get("get", {})
        assert get_method.get("summary") == "Get floor by ID"

    def test_floors_put_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        put_method = data["paths"]["/api/v1/floors/{floor_id}"].get("put", {})
        assert put_method.get("summary") == "Update a floor"

    def test_floors_delete_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        delete_method = data["paths"]["/api/v1/floors/{floor_id}"].get("delete", {})
        assert delete_method.get("summary") == "Delete a floor"

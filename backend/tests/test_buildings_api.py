from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.building import BuildingResponse
from tests.auth_support import bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))


def _building_response(parcel_id: str | None = None) -> BuildingResponse:
    return BuildingResponse(
        id=str(uuid4()),
        parcel_id=str(parcel_id or uuid4()),
        building_identifier="BLD-001",
        name="Tower A",
        building_type="residential",
        construction_status="completed",
        footprint_geometry=None,
        created_at="2026-09-20T00:00:00+00:00",
        updated_at="2026-09-20T00:00:00+00:00",
    )


class TestCreateBuilding:
    @patch("app.api.v1.buildings.create_building")
    def test_create_building_success(self, mock_create):
        parcel_id = uuid4()
        building = _building_response(str(parcel_id))
        mock_create.return_value = building
        response = client.post(
            f"/api/v1/parcels/{parcel_id}/buildings",
            json={
                "building_identifier": "BLD-001",
                "name": "Tower A",
                "building_type": "residential",
                "construction_status": "completed",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["parcel_id"] == str(parcel_id)
        assert data["building_identifier"] == "BLD-001"
        assert data["building_type"] == "residential"
        assert data["construction_status"] == "completed"

    @patch("app.api.v1.buildings.create_building")
    def test_create_building_parcel_not_found(self, mock_create):
        mock_create.side_effect = ValueError("Parcel not found")
        response = client.post(
            f"/api/v1/parcels/{uuid4()}/buildings",
            json={
                "building_identifier": "BLD-001",
                "building_type": "residential",
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"
        assert data["message"] == "Parcel not found"

    @patch("app.api.v1.buildings.create_building")
    def test_create_building_with_footprint(self, mock_create):
        parcel_id = uuid4()
        building = _building_response(str(parcel_id))
        building.footprint_geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.5, 12.9],
                    [77.6, 12.9],
                    [77.6, 13.0],
                    [77.5, 13.0],
                    [77.5, 12.9],
                ]
            ],
        }
        mock_create.return_value = building
        response = client.post(
            f"/api/v1/parcels/{parcel_id}/buildings",
            json={
                "building_identifier": "BLD-001",
                "building_type": "commercial",
                "footprint_geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [77.5, 12.9],
                            [77.6, 12.9],
                            [77.6, 13.0],
                            [77.5, 13.0],
                            [77.5, 12.9],
                        ]
                    ],
                },
            },
        )
        assert response.status_code == 201
        assert response.json()["footprint_geometry"]["type"] == "Polygon"

    def test_create_building_invalid_building_type(self):
        response = client.post(
            f"/api/v1/parcels/{uuid4()}/buildings",
            json={
                "building_identifier": "BLD-001",
                "building_type": "skyscraper",
            },
        )
        assert response.status_code == 422

    def test_create_building_missing_required_fields(self):
        response = client.post(
            f"/api/v1/parcels/{uuid4()}/buildings",
            json={"name": "No identifier"},
        )
        assert response.status_code == 422

    @patch("app.api.v1.buildings.create_building")
    def test_create_building_invalid_footprint_type(self, mock_create):
        mock_create.side_effect = ValueError("footprint_geometry must be a GeoJSON Polygon")
        response = client.post(
            f"/api/v1/parcels/{uuid4()}/buildings",
            json={
                "building_identifier": "BLD-001",
                "building_type": "residential",
                "footprint_geometry": {"type": "Point", "coordinates": [0, 0]},
            },
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"


class TestListBuildings:
    @patch("app.api.v1.buildings.list_buildings")
    def test_list_buildings_success(self, mock_list):
        parcel_id = uuid4()
        mock_list.return_value = [_building_response(str(parcel_id))]
        response = client.get(f"/api/v1/parcels/{parcel_id}/buildings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["building_identifier"] == "BLD-001"

    @patch("app.api.v1.buildings.list_buildings")
    def test_list_buildings_parcel_not_found(self, mock_list):
        mock_list.side_effect = ValueError("Parcel not found")
        response = client.get(f"/api/v1/parcels/{uuid4()}/buildings")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"

    @patch("app.api.v1.buildings.list_buildings")
    def test_list_buildings_empty(self, mock_list):
        mock_list.return_value = []
        response = client.get(f"/api/v1/parcels/{uuid4()}/buildings")
        assert response.status_code == 200
        assert response.json() == []


class TestGetBuilding:
    @patch("app.api.v1.buildings.get_building")
    def test_get_building_success(self, mock_get):
        building = _building_response()
        mock_get.return_value = building
        response = client.get(f"/api/v1/buildings/{uuid4()}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == building.id
        assert data["name"] == "Tower A"

    @patch("app.api.v1.buildings.get_building")
    def test_get_building_not_found(self, mock_get):
        mock_get.side_effect = ValueError("Building not found")
        response = client.get(f"/api/v1/buildings/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"


class TestUpdateBuilding:
    @patch("app.api.v1.buildings.update_building")
    def test_update_building_success(self, mock_update):
        building = _building_response()
        mock_update.return_value = building
        response = client.put(
            f"/api/v1/buildings/{uuid4()}",
            json={"name": "Tower B", "construction_status": "under_construction"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Tower A"

    @patch("app.api.v1.buildings.update_building")
    def test_update_building_not_found(self, mock_update):
        mock_update.side_effect = ValueError("Building not found")
        response = client.put(
            f"/api/v1/buildings/{uuid4()}",
            json={"name": "Tower B"},
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"

    def test_update_building_invalid_building_type(self):
        response = client.put(
            f"/api/v1/buildings/{uuid4()}",
            json={"building_type": "castle"},
        )
        assert response.status_code == 422


class TestDeleteBuilding:
    @patch("app.api.v1.buildings.delete_building")
    def test_delete_building_success(self, mock_delete):
        response = client.delete(f"/api/v1/buildings/{uuid4()}")
        assert response.status_code == 204
        assert response.content == b""

    @patch("app.api.v1.buildings.delete_building")
    def test_delete_building_not_found(self, mock_delete):
        mock_delete.side_effect = ValueError("Building not found")
        response = client.delete(f"/api/v1/buildings/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"


class TestOpenAPIDocumentation:
    def test_openapi_json_has_buildings_tag(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        tag_names = [t["name"] for t in response.json().get("tags", [])]
        assert "Buildings" in tag_names

    def test_openapi_json_has_buildings_paths(self):
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        assert "/api/v1/parcels/{parcel_id}/buildings" in paths
        assert "/api/v1/buildings/{building_id}" in paths

    def test_buildings_post_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        post_method = data["paths"]["/api/v1/parcels/{parcel_id}/buildings"].get("post", {})
        assert post_method.get("summary") == "Create a building"
        assert "201" in post_method.get("responses", {})
        assert "404" in post_method.get("responses", {})

    def test_buildings_get_list_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/parcels/{parcel_id}/buildings"].get("get", {})
        assert get_method.get("summary") == "List buildings of a parcel"

    def test_buildings_get_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/buildings/{building_id}"].get("get", {})
        assert get_method.get("summary") == "Get building by ID"

    def test_buildings_put_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        put_method = data["paths"]["/api/v1/buildings/{building_id}"].get("put", {})
        assert put_method.get("summary") == "Update a building"
        assert "200" in put_method.get("responses", {})

    def test_buildings_delete_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        delete_method = data["paths"]["/api/v1/buildings/{building_id}"].get("delete", {})
        assert delete_method.get("summary") == "Delete a building"
        assert "204" in delete_method.get("responses", {})

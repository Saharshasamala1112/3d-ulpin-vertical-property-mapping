from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_support import bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))


SAMPLE_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.5, 12.9],
                [77.6, 12.9],
                [77.6, 13.0],
                [77.5, 13.0],
                [77.5, 12.9],
            ]
        ]
    ],
}


class TestCreateParcel:
    @patch("app.api.v1.parcels.create_parcel")
    def test_create_parcel_success(self, mock_create):
        parcel_id = uuid4()
        from app.schemas.parcel import (
            GeoJSONFeature,
            GeoJSONGeometry,
            ParcelResponse,
        )

        mock_create.return_value = GeoJSONFeature(
            id=str(parcel_id),
            geometry=GeoJSONGeometry(
                type="MultiPolygon",
                coordinates=SAMPLE_GEOMETRY["coordinates"],
            ),
            properties=ParcelResponse(
                id=str(parcel_id),
                parcel_identifier="PARCEL-001",
                ulpin="ULPIN-001",
                area_sqm=1500.0,
                status="draft",
                metadata={"zone": "residential"},
                created_at="2026-09-19T00:00:00+00:00",
                updated_at="2026-09-19T00:00:00+00:00",
            ),
        )
        response = client.post(
            "/api/v1/parcels",
            json={
                "parcel_identifier": "PARCEL-001",
                "ulpin": "ULPIN-001",
                "geometry": SAMPLE_GEOMETRY,
                "area_sqm": 1500.0,
                "status": "draft",
                "metadata": {"zone": "residential"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "Feature"
        assert data["properties"]["parcel_identifier"] == "PARCEL-001"
        assert data["properties"]["ulpin"] == "ULPIN-001"

    @patch("app.api.v1.parcels.create_parcel")
    def test_create_parcel_duplicate(self, mock_create):
        mock_create.side_effect = ValueError(
            "Parcel with this ulpin or parcel_identifier already exists"
        )
        response = client.post(
            "/api/v1/parcels",
            json={
                "parcel_identifier": "PARCEL-001",
                "ulpin": "ULPIN-001",
                "geometry": SAMPLE_GEOMETRY,
                "area_sqm": 1500.0,
            },
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error_code"] == "DUPLICATE_PARCEL"

    def test_create_parcel_validation_error(self):
        response = client.post(
            "/api/v1/parcels",
            json={
                "parcel_identifier": "",
                "ulpin": "ULPIN-001",
                "geometry": SAMPLE_GEOMETRY,
                "area_sqm": 1500.0,
            },
        )
        assert response.status_code == 422

    def test_create_parcel_missing_geometry(self):
        response = client.post(
            "/api/v1/parcels",
            json={
                "parcel_identifier": "PARCEL-001",
                "ulpin": "ULPIN-001",
                "area_sqm": 1500.0,
            },
        )
        assert response.status_code == 422

    def test_create_parcel_negative_area(self):
        response = client.post(
            "/api/v1/parcels",
            json={
                "parcel_identifier": "PARCEL-001",
                "ulpin": "ULPIN-001",
                "geometry": SAMPLE_GEOMETRY,
                "area_sqm": -100,
            },
        )
        assert response.status_code == 422


class TestGetParcel:
    @patch("app.api.v1.parcels.get_parcel")
    def test_get_parcel_success(self, mock_get):
        parcel_id = uuid4()
        from app.schemas.parcel import (
            GeoJSONFeature,
            GeoJSONGeometry,
            ParcelResponse,
        )

        mock_get.return_value = GeoJSONFeature(
            id=str(parcel_id),
            geometry=GeoJSONGeometry(
                type="MultiPolygon",
                coordinates=SAMPLE_GEOMETRY["coordinates"],
            ),
            properties=ParcelResponse(
                id=str(parcel_id),
                parcel_identifier="PARCEL-001",
                ulpin="ULPIN-001",
                area_sqm=1500.0,
                status="active",
                metadata=None,
                created_at="2026-09-19T00:00:00+00:00",
                updated_at="2026-09-19T00:00:00+00:00",
            ),
        )
        response = client.get(f"/api/v1/parcels/{parcel_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "Feature"
        assert data["id"] == str(parcel_id)
        assert data["geometry"]["type"] == "MultiPolygon"
        assert data["properties"]["status"] == "active"

    @patch("app.api.v1.parcels.get_parcel")
    def test_get_parcel_not_found(self, mock_get):
        mock_get.side_effect = ValueError("Parcel not found")
        response = client.get(f"/api/v1/parcels/{uuid4()}")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"


class TestListParcels:
    @patch("app.api.v1.parcels.list_parcels")
    def test_list_parcels_success(self, mock_list):
        from app.schemas.parcel import (
            GeoJSONFeature,
            GeoJSONGeometry,
            PaginationMeta,
            ParcelListResponse,
            ParcelResponse,
        )

        parcel_id = uuid4()
        mock_list.return_value = ParcelListResponse(
            data=[
                GeoJSONFeature(
                    id=str(parcel_id),
                    geometry=GeoJSONGeometry(
                        type="MultiPolygon",
                        coordinates=SAMPLE_GEOMETRY["coordinates"],
                    ),
                    properties=ParcelResponse(
                        id=str(parcel_id),
                        parcel_identifier="PARCEL-001",
                        ulpin="ULPIN-001",
                        area_sqm=1500.0,
                        status="draft",
                        metadata=None,
                        created_at="2026-09-19T00:00:00+00:00",
                        updated_at="2026-09-19T00:00:00+00:00",
                    ),
                )
            ],
            meta=PaginationMeta(page=1, per_page=20, total=1, total_pages=1),
        )
        response = client.get("/api/v1/parcels")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["page"] == 1
        assert data["meta"]["total"] == 1
        assert len(data["data"]) == 1

    @patch("app.api.v1.parcels.list_parcels")
    def test_list_parcels_with_status_filter(self, mock_list):
        from app.schemas.parcel import PaginationMeta, ParcelListResponse

        mock_list.return_value = ParcelListResponse(
            data=[],
            meta=PaginationMeta(page=1, per_page=20, total=0, total_pages=0),
        )
        response = client.get("/api/v1/parcels?status=active")
        assert response.status_code == 200
        mock_list.assert_called_once()

    @patch("app.api.v1.parcels.list_parcels")
    def test_list_parcels_with_bbox(self, mock_list):
        from app.schemas.parcel import PaginationMeta, ParcelListResponse

        mock_list.return_value = ParcelListResponse(
            data=[],
            meta=PaginationMeta(page=1, per_page=20, total=0, total_pages=0),
        )
        response = client.get("/api/v1/parcels?min_lon=77.0&min_lat=12.0&max_lon=78.0&max_lat=13.5")
        assert response.status_code == 200

    def test_list_parcels_invalid_page(self):
        response = client.get("/api/v1/parcels?page=0")
        assert response.status_code == 422

    def test_list_parcels_invalid_per_page(self):
        response = client.get("/api/v1/parcels?per_page=0")
        assert response.status_code == 422


class TestUpdateParcel:
    @patch("app.api.v1.parcels.update_parcel")
    def test_update_parcel_success(self, mock_update):
        parcel_id = uuid4()
        from app.schemas.parcel import (
            GeoJSONFeature,
            GeoJSONGeometry,
            ParcelResponse,
        )

        mock_update.return_value = GeoJSONFeature(
            id=str(parcel_id),
            geometry=GeoJSONGeometry(
                type="MultiPolygon",
                coordinates=SAMPLE_GEOMETRY["coordinates"],
            ),
            properties=ParcelResponse(
                id=str(parcel_id),
                parcel_identifier="PARCEL-UPDATED",
                ulpin="ULPIN-001",
                area_sqm=2000.0,
                status="active",
                metadata=None,
                created_at="2026-09-19T00:00:00+00:00",
                updated_at="2026-09-19T01:00:00+00:00",
            ),
        )
        response = client.put(
            f"/api/v1/parcels/{parcel_id}",
            json={
                "parcel_identifier": "PARCEL-UPDATED",
                "area_sqm": 2000.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["properties"]["parcel_identifier"] == "PARCEL-UPDATED"
        assert data["properties"]["area_sqm"] == 2000.0

    @patch("app.api.v1.parcels.update_parcel")
    def test_update_parcel_not_found(self, mock_update):
        mock_update.side_effect = ValueError("Parcel not found")
        response = client.put(
            f"/api/v1/parcels/{uuid4()}",
            json={"parcel_identifier": "UPDATED"},
        )
        assert response.status_code == 404

    @patch("app.api.v1.parcels.update_parcel")
    def test_update_parcel_duplicate(self, mock_update):
        mock_update.side_effect = ValueError(
            "Parcel with this ulpin or parcel_identifier already exists"
        )
        response = client.put(
            f"/api/v1/parcels/{uuid4()}",
            json={"ulpin": "DUPLICATE-ULPIN"},
        )
        assert response.status_code == 409


class TestDeleteParcel:
    @patch("app.api.v1.parcels.delete_parcel")
    def test_delete_parcel_success(self, mock_delete):
        response = client.delete(f"/api/v1/parcels/{uuid4()}")
        assert response.status_code == 204

    @patch("app.api.v1.parcels.delete_parcel")
    def test_delete_parcel_not_found(self, mock_delete):
        mock_delete.side_effect = ValueError("Parcel not found")
        response = client.delete(f"/api/v1/parcels/{uuid4()}")
        assert response.status_code == 404


class TestGetULPIN:
    @patch("app.api.v1.parcels.get_ulpin_for_parcel")
    def test_get_ulpin_success(self, mock_get_ulpin):
        parcel_id = uuid4()
        ulpin_id = uuid4()
        from app.schemas.parcel import ULPINResponse

        mock_get_ulpin.return_value = ULPINResponse(
            id=str(ulpin_id),
            parcel_id=str(parcel_id),
            ulpin_code="ULPIN-CODE-001",
            issued_date="2026-09-19T00:00:00+00:00",
            issuing_authority="Land Registry",
            checksum="abc123def456",
        )
        response = client.get(f"/api/v1/parcels/{parcel_id}/ulpin")
        assert response.status_code == 200
        data = response.json()
        assert data["ulpin_code"] == "ULPIN-CODE-001"
        assert data["issuing_authority"] == "Land Registry"

    @patch("app.api.v1.parcels.get_ulpin_for_parcel")
    def test_get_ulpin_not_found(self, mock_get_ulpin):
        mock_get_ulpin.side_effect = ValueError("ULPIN not found for this parcel")
        response = client.get(f"/api/v1/parcels/{uuid4()}/ulpin")
        assert response.status_code == 404


class TestOpenAPIDocumentation:
    def test_openapi_docs_accessible(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_has_parcels_tag(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        tag_names = [t["name"] for t in data.get("tags", [])]
        assert "Parcels" in tag_names

    def test_openapi_json_has_parcels_paths(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        paths = data.get("paths", {})
        assert "/api/v1/parcels" in paths
        assert "/api/v1/parcels/{parcel_id}" in paths
        assert "/api/v1/parcels/{parcel_id}/ulpin" in paths

    def test_parcels_post_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        post_method = data["paths"]["/api/v1/parcels"].get("post", {})
        assert post_method.get("summary") == "Create a new parcel"
        assert "201" in post_method.get("responses", {})

    def test_parcels_get_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        get_method = data["paths"]["/api/v1/parcels"].get("get", {})
        assert get_method.get("summary") == "List parcels"

    def test_parcels_put_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        put_method = data["paths"]["/api/v1/parcels/{parcel_id}"].get("put", {})
        assert put_method.get("summary") == "Update a parcel"

    def test_parcels_delete_method_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        delete_method = data["paths"]["/api/v1/parcels/{parcel_id}"].get("delete", {})
        assert delete_method.get("summary") == "Soft-delete a parcel"

    def test_ulpin_endpoint_documented(self):
        response = client.get("/openapi.json")
        data = response.json()
        ulpin_method = data["paths"]["/api/v1/parcels/{parcel_id}/ulpin"].get("get", {})
        assert ulpin_method.get("summary") == "Get ULPIN for a parcel"

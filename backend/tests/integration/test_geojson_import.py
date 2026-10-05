from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.building import Building
from app.models.parcel import Parcel
from app.models.user import UserRole
from app.schemas.geojson_import import MAX_IMPORT_BYTES

pytestmark = pytest.mark.integration

PARCEL_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
}

BUILDING_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[77.51, 12.91], [77.52, 12.91], [77.52, 12.92], [77.51, 12.92], [77.51, 12.91]]
    ],
}


@pytest.fixture
def import_client(
    client: TestClient,
    app_instance,
) -> TestClient:
    def editor_user():
        return SimpleNamespace(role=UserRole.EDITOR)

    app_instance.dependency_overrides[get_current_user] = editor_user
    try:
        yield client
    finally:
        app_instance.dependency_overrides.pop(get_current_user, None)


def parcel_feature(
    *,
    ulpin: str = "GEOSX00001",
    identifier: str = "IMPORT-PARCEL-1",
    geometry: dict = PARCEL_POLYGON,
    area: float = 1000,
) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "ulpin": ulpin,
            "parcel_identifier": identifier,
            "area_sqm": area,
            "status": "active",
        },
        "geometry": geometry,
    }


def test_parcel_import_dry_run_mixed_batch_then_upsert_and_skip(
    import_client: TestClient,
    db_session: Session,
) -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            parcel_feature(),
            parcel_feature(ulpin="INVALID", identifier="IMPORT-PARCEL-2"),
        ],
    }
    before = db_session.query(Parcel).count()

    preview = import_client.post("/api/v1/parcels/import", json=collection)

    assert preview.status_code == 200, preview.text
    report = preview.json()
    assert (report["created"], report["updated"], report["skipped"], report["failed"]) == (
        1,
        0,
        0,
        1,
    )
    assert report["features"][1]["index"] == 2
    assert "ULPIN" in report["features"][1]["reason"]
    assert db_session.query(Parcel).count() == before

    imported = import_client.post("/api/v1/parcels/import?dry_run=false", json=collection)
    assert imported.status_code == 200, imported.text
    assert (imported.json()["created"], imported.json()["failed"]) == (1, 1)
    assert db_session.query(Parcel).count() == before + 1

    repeated = import_client.post("/api/v1/parcels/import?dry_run=false", json=collection)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["created"] == 0
    assert repeated.json()["skipped"] == 1
    assert db_session.query(Parcel).count() == before + 1


def test_parcel_import_supports_configured_ulpin_property_and_update(
    import_client: TestClient,
) -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                **parcel_feature(),
                "properties": {
                    "cadastre_id": "GEOSX00002",
                    "name": "Parcel by name",
                    "area_sqm": 1200,
                },
            }
        ],
    }
    first = import_client.post(
        "/api/v1/parcels/import?dry_run=false&ulpin_property=cadastre_id",
        json=collection,
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1

    collection["features"][0]["properties"]["area_sqm"] = 1300
    second = import_client.post(
        "/api/v1/parcels/import?dry_run=false&ulpin_property=cadastre_id",
        json=collection,
    )
    assert second.status_code == 200, second.text
    assert second.json()["updated"] == 1


def test_building_import_continues_when_one_parcel_is_missing(
    import_client: TestClient,
    db_session: Session,
    parcel,
) -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "building_identifier": "IMPORT-BUILDING-1",
                    "parcel_id": str(parcel.id),
                    "building_type": "residential",
                    "construction_status": "completed",
                },
                "geometry": BUILDING_POLYGON,
            },
            {
                "type": "Feature",
                "properties": {
                    "building_identifier": "IMPORT-BUILDING-2",
                    "parcel_id": "00000000-0000-0000-0000-000000000001",
                },
                "geometry": BUILDING_POLYGON,
            },
        ],
    }

    response = import_client.post(
        "/api/v1/buildings/import?dry_run=false",
        json=collection,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["created"], body["failed"]) == (1, 1)
    assert "does not exist" in body["features"][1]["reason"]
    assert db_session.query(Building).filter_by(parcel_id=parcel.id).count() == 1

    repeated = import_client.post(
        f"/api/v1/buildings/import?dry_run=false&parcel_id={parcel.id}",
        json={
            "type": "FeatureCollection",
            "features": [collection["features"][0]],
        },
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["skipped"] == 1
    assert db_session.query(Building).filter_by(parcel_id=parcel.id).count() == 1


def test_import_endpoints_reject_reader_role(
    client: TestClient,
    app_instance,
) -> None:
    app_instance.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.READER
    )
    collection = {"type": "FeatureCollection", "features": [parcel_feature()]}
    try:
        parcel_response = client.post("/api/v1/parcels/import", json=collection)
        building_response = client.post("/api/v1/buildings/import", json=collection)
    finally:
        app_instance.dependency_overrides.pop(get_current_user, None)

    assert parcel_response.status_code == 403
    assert building_response.status_code == 403


def test_import_endpoints_document_limits_and_request_envelopes(import_client: TestClient) -> None:
    schema = import_client.get("/openapi.json").json()

    for path in ("/api/v1/parcels/import", "/api/v1/buildings/import"):
        operation = schema["paths"][path]["post"]
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert request_schema["properties"]["features"]["maxItems"] == 500
        assert "10 MiB" in operation["description"]


def test_import_rejects_oversized_request_before_parsing(import_client: TestClient) -> None:
    response = import_client.post(
        "/api/v1/parcels/import",
        content=b" " * (MAX_IMPORT_BYTES + 1),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    # Errors use the shared envelope documented in docs/api.md, so the code
    # arrives as `error_code` rather than nested under a FastAPI `detail`.
    assert response.json()["error_code"] == "IMPORT_TOO_LARGE"

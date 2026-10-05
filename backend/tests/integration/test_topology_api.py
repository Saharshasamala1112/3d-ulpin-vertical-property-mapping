from __future__ import annotations

import time
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.integration.factories import (
    building_factory,
    floor_factory,
    property_geometry_factory,
    unit_factory,
)

pytestmark = pytest.mark.integration


def test_building_validation_returns_full_pass_report(client, db_session):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    unit = unit_factory(db_session, floor=floor, geometry=False)
    property_geometry_factory(db_session, unit)

    response = client.post(f"/api/v1/topology/validate/building/{building.id}")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "status": "passed",
            "valid": True,
            "geometry_error_count": 0,
            "overlap_count": 0,
            "gap_count": 0,
            "elevation_error_count": 0,
        },
        "geometry_errors": [],
        "overlap_results": [],
        "gap_results": [],
        "elevation_errors": [],
    }


def test_building_validation_combines_geometry_overlap_gap_and_elevation_results(
    client, db_session
):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    units = [
        unit_factory(db_session, floor=floor, unit_identifier=f"TOPOLOGY-{index}")
        for index in range(3)
    ]
    property_geometry_factory(
        db_session,
        units[0],
        x_min=Decimal("0"),
        x_max=Decimal("2"),
        y_min=Decimal("0"),
        y_max=Decimal("2"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )
    property_geometry_factory(
        db_session,
        units[1],
        x_min=Decimal("1"),
        x_max=Decimal("3"),
        y_min=Decimal("0"),
        y_max=Decimal("2"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )
    property_geometry_factory(
        db_session,
        units[2],
        x_min=Decimal("4"),
        x_max=Decimal("5"),
        y_min=Decimal("0"),
        y_max=Decimal("2"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )

    response = client.post(f"/api/v1/topology/validate/building/{building.id}")

    assert response.status_code == 200
    report = response.json()
    assert report["summary"] == {
        "status": "failed",
        "valid": False,
        "geometry_error_count": 0,
        "overlap_count": 1,
        "gap_count": 1,
        "elevation_error_count": 0,
    }
    assert len(report["overlap_results"]) == 1
    assert Decimal(report["overlap_results"][0]["overlap_volume"]) == Decimal("6")
    assert len(report["gap_results"]) == 1
    assert report["gap_results"][0]["gap_direction"] == "x"


def test_unit_validation_reports_missing_geometry_and_validates_independently(client, db_session):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    unit = unit_factory(db_session, floor=floor, geometry=False)

    missing_geometry = client.post(f"/api/v1/topology/validate/unit/{unit.id}")

    assert missing_geometry.status_code == 200
    assert missing_geometry.json()["summary"]["status"] == "failed"
    assert missing_geometry.json()["geometry_errors"][0]["code"] == "MISSING_GEOMETRY"

    property_geometry_factory(db_session, unit)
    valid_geometry = client.post(f"/api/v1/topology/validate/unit/{unit.id}")

    assert valid_geometry.status_code == 200
    assert valid_geometry.json()["summary"]["status"] == "passed"


def test_overlap_endpoint_accepts_unit_ids(client, db_session):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    units = [unit_factory(db_session, floor=floor) for _ in range(2)]
    for unit in units:
        property_geometry_factory(db_session, unit)

    response = client.post(
        "/api/v1/topology/validate/overlaps",
        json={"unit_ids": [str(unit.id) for unit in units]},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["overlap_count"] == 1
    assert response.json()["summary"]["status"] == "failed"


def test_gap_endpoint_accepts_unit_ids_and_custom_tolerances(client, db_session):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    first = unit_factory(db_session, floor=floor, unit_identifier="API-GAP-A")
    second = unit_factory(db_session, floor=floor, unit_identifier="API-GAP-B")
    property_geometry_factory(
        db_session,
        first,
        x_min=Decimal("0"),
        x_max=Decimal("1"),
    )
    property_geometry_factory(
        db_session,
        second,
        x_min=Decimal("1.2"),
        x_max=Decimal("2.2"),
    )

    response = client.post(
        "/api/v1/topology/validate/gaps",
        json={
            "unit_ids": [str(first.id), str(second.id)],
            "minimum_gap": 0.1,
            "maximum_gap": 0.5,
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"]["gap_count"] == 1
    assert Decimal(response.json()["gap_results"][0]["gap_distance"]) == Decimal("0.2")


def test_gap_endpoint_rejects_invalid_tolerance_range(client):
    response = client.post(
        "/api/v1/topology/validate/gaps",
        json={"unit_ids": [], "minimum_gap": 1, "maximum_gap": 1},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("path", "message"),
    (
        (f"/api/v1/topology/validate/building/{uuid4()}", "Building not found"),
        (f"/api/v1/topology/validate/unit/{uuid4()}", "Unit not found"),
    ),
)
def test_validation_endpoints_return_not_found_for_unknown_resources(client, path, message):
    response = client.post(path)

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"
    assert response.json()["message"] == message


@pytest.mark.parametrize("path", ("/overlaps", "/gaps"))
def test_pairwise_endpoints_return_not_found_for_unknown_unit_ids(client, path):
    response = client.post(
        f"/api/v1/topology/validate{path}",
        json={"unit_ids": [str(uuid4())]},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_openapi_documents_all_topology_endpoints(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/topology/validate/building/{building_id}" in paths
    assert "/api/v1/topology/validate/unit/{unit_id}" in paths
    assert "/api/v1/topology/validate/overlaps" in paths
    assert "/api/v1/topology/validate/gaps" in paths


def test_building_validation_completes_within_five_seconds_for_one_hundred_units(
    client, db_session
):
    building = building_factory(db_session)
    floor = floor_factory(db_session, building=building)
    for index in range(100):
        unit = unit_factory(
            db_session,
            floor=floor,
            unit_identifier=f"PERF-{index:03d}",
        )
        property_geometry_factory(
            db_session,
            unit,
            x_min=Decimal(index * 2),
            x_max=Decimal(index * 2 + 1),
            y_min=Decimal("0"),
            y_max=Decimal("1"),
            z_min=Decimal("0"),
            z_max=Decimal("3"),
        )

    started = time.perf_counter()
    response = client.post(f"/api/v1/topology/validate/building/{building.id}")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert response.json()["summary"]["gap_count"] == 99
    assert elapsed < 5

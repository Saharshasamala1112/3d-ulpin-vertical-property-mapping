from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.topology import build_topology_report
from tests.auth_support import bearer_headers


@pytest.fixture
def topology_client():
    return TestClient(app, headers=bearer_headers("admin"))


def test_building_validation_route_returns_report(topology_client):
    building_id = uuid4()
    report = build_topology_report()
    with patch("app.api.v1.topology.validate_building_topology", return_value=report) as validate:
        response = topology_client.post(f"/api/v1/topology/validate/building/{building_id}")

    assert response.status_code == 200
    assert response.json()["summary"]["status"] == "passed"
    validate.assert_called_once()
    assert validate.call_args.args[1] == building_id


def test_unit_validation_route_returns_report(topology_client):
    unit_id = uuid4()
    report = build_topology_report()
    with patch("app.api.v1.topology.validate_unit_topology", return_value=report) as validate:
        response = topology_client.post(f"/api/v1/topology/validate/unit/{unit_id}")

    assert response.status_code == 200
    validate.assert_called_once()
    assert validate.call_args.args[1] == unit_id


def test_overlap_route_accepts_unit_ids(topology_client):
    unit_ids = [uuid4(), uuid4()]
    report = build_topology_report()
    with patch("app.api.v1.topology.validate_unit_overlaps", return_value=report) as validate:
        response = topology_client.post(
            "/api/v1/topology/validate/overlaps",
            json={"unit_ids": [str(unit_id) for unit_id in unit_ids]},
        )

    assert response.status_code == 200
    assert validate.call_args.args[1].unit_ids == unit_ids


def test_gap_route_accepts_unit_ids_and_thresholds(topology_client):
    unit_ids = [uuid4(), uuid4()]
    report = build_topology_report()
    with patch("app.api.v1.topology.validate_unit_gaps", return_value=report) as validate:
        response = topology_client.post(
            "/api/v1/topology/validate/gaps",
            json={
                "unit_ids": [str(unit_id) for unit_id in unit_ids],
                "minimum_gap": 0.02,
                "maximum_gap": 0.5,
            },
        )

    assert response.status_code == 200
    assert validate.call_args.args[1].unit_ids == unit_ids
    assert validate.call_args.kwargs["minimum_gap"] == Decimal("0.02")
    assert validate.call_args.kwargs["maximum_gap"] == Decimal("0.5")


def test_gap_route_rejects_invalid_threshold_order(topology_client):
    with patch("app.api.v1.topology.validate_unit_gaps") as validate:
        response = topology_client.post(
            "/api/v1/topology/validate/gaps",
            json={"unit_ids": [], "minimum_gap": 1, "maximum_gap": 1},
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    validate.assert_not_called()


def test_topology_openapi_has_all_endpoints_and_report_schema(topology_client):
    openapi = topology_client.get("/openapi.json").json()

    assert {
        "/api/v1/topology/validate/building/{building_id}",
        "/api/v1/topology/validate/unit/{unit_id}",
        "/api/v1/topology/validate/overlaps",
        "/api/v1/topology/validate/gaps",
    } <= set(openapi["paths"])
    report_schema = openapi["components"]["schemas"]["TopologyValidationReport"]
    assert {
        "summary",
        "geometry_errors",
        "overlap_results",
        "gap_results",
        "elevation_errors",
    } <= set(report_schema["properties"])

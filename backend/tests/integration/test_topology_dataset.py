from __future__ import annotations

import pytest

from tests.fixtures.topology_dataset import seed_topology_dataset

pytestmark = pytest.mark.integration


def test_seeded_topology_scenarios_are_idempotent_and_match_expected_reports(client, db_session):
    dataset = seed_topology_dataset(db_session)
    repeated_dataset = seed_topology_dataset(db_session)

    assert dataset == repeated_dataset

    for scenario in dataset.values():
        response = client.post(f"/api/v1/topology/validate/building/{scenario.building_id}")

        assert response.status_code == 200, scenario.spec.key
        report = response.json()
        assert report["summary"]["geometry_error_count"] == len(scenario.spec.geometry_codes), (
            scenario.spec.key
        )
        assert report["summary"]["overlap_count"] == scenario.spec.overlap_count, scenario.spec.key
        assert report["summary"]["gap_count"] == scenario.spec.gap_count, scenario.spec.key
        assert report["summary"]["elevation_error_count"] >= len(scenario.spec.elevation_codes), (
            scenario.spec.key
        )
        assert {error["code"] for error in report["geometry_errors"]} == (
            scenario.spec.geometry_codes
        ), scenario.spec.key
        assert {error["code"] for error in report["elevation_errors"]} >= (
            scenario.spec.elevation_codes
        ), scenario.spec.key

    mixed_report = client.post(
        f"/api/v1/topology/validate/building/{dataset['mixed'].building_id}"
    ).json()
    assert mixed_report["summary"]["valid"] is False
    assert mixed_report["summary"]["geometry_error_count"] > 0
    assert mixed_report["summary"]["overlap_count"] > 0
    assert mixed_report["summary"]["gap_count"] > 0
    assert mixed_report["summary"]["elevation_error_count"] > 0


def test_seeded_dataset_unit_endpoint_accepts_stable_unit_ids(client, db_session):
    dataset = seed_topology_dataset(db_session)

    response = client.post(f"/api/v1/topology/validate/unit/{dataset['valid'].unit_ids[0]}")

    assert response.status_code == 200
    assert response.json()["summary"]["valid"] is True

from __future__ import annotations

import pytest

from app.validators.geometry3d_validator import validate_geometry
from tests.fixtures.topology_dataset import (
    GEOMETRY_VALIDATION_CASES,
    SCENARIOS,
    stable_id,
)


@pytest.mark.parametrize(
    ("name", "geometry", "expected_code"),
    GEOMETRY_VALIDATION_CASES,
    ids=[case[0] for case in GEOMETRY_VALIDATION_CASES],
)
def test_dataset_invalid_geometry_examples_trigger_expected_codes(name, geometry, expected_code):
    result = validate_geometry(geometry)

    assert result.valid is False, name
    assert expected_code in {issue.code for issue in result.errors}


def test_dataset_scenario_ids_are_deterministic_and_unique():
    ids = [stable_id(f"{scenario.key}:building") for scenario in SCENARIOS]

    assert ids == [stable_id(f"{scenario.key}:building") for scenario in SCENARIOS]
    assert len(ids) == len(set(ids))

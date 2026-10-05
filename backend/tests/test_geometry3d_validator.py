from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.geometry3d import GeometryValidationInput
from app.validators.geometry3d_validator import validate_geometry


def _geometry(**overrides: Decimal | None) -> PropertyGeometry:
    coordinates = {
        "x_min": Decimal("0"),
        "x_max": Decimal("10"),
        "y_min": Decimal("0"),
        "y_max": Decimal("5"),
        "z_min": Decimal("0"),
        "z_max": Decimal("3"),
    }
    coordinates.update(overrides)
    return PropertyGeometry(
        unit_id=uuid.uuid4(),
        geometry_type=GeometryType.AABB,
        **coordinates,
    )


def test_valid_geometry_returns_structured_empty_result():
    geometry = _geometry()

    result = validate_geometry(geometry)

    assert result.valid is True
    assert result.errors == []
    assert result.warnings == []
    assert result.model_dump() == {"valid": True, "errors": [], "warnings": []}


def test_valid_geometry_is_deterministic_and_idempotent():
    geometry = _geometry()

    assert validate_geometry(geometry) == validate_geometry(geometry)


def test_none_geometry_returns_missing_geometry_error():
    result = validate_geometry(None)

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [
        ("MISSING_GEOMETRY", "geometry")
    ]


@pytest.mark.parametrize(
    "coordinate",
    ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"),
)
def test_missing_bounding_box_coordinate_is_reported(coordinate: str):
    result = validate_geometry(_geometry(**{coordinate: None}))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [
        ("MISSING_GEOMETRY", coordinate)
    ]


@pytest.mark.parametrize("axis", ("x", "y", "z"))
def test_inverted_dimension_returns_invalid_dimensions(axis: str):
    result = validate_geometry(_geometry(**{f"{axis}_min": Decimal("100")}))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [("INVALID_DIMENSIONS", axis)]


@pytest.mark.parametrize("axis", ("x", "y", "z"))
def test_zero_dimension_returns_zero_volume(axis: str):
    result = validate_geometry(_geometry(**{f"{axis}_max": Decimal("0")}))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [("ZERO_VOLUME", axis)]


def test_dimension_below_default_threshold_returns_specific_error():
    result = validate_geometry(_geometry(x_max=Decimal("0.0005")))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [
        ("DIMENSION_BELOW_THRESHOLD", "x")
    ]


def test_minimum_dimension_is_configurable_per_validation_run():
    geometry = _geometry(x_max=Decimal("0.5"))

    assert validate_geometry(geometry, minimum_dimension=Decimal("0.1")).valid is True
    result = validate_geometry(geometry, minimum_dimension=Decimal("0.6"))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [
        ("DIMENSION_BELOW_THRESHOLD", "x")
    ]


@pytest.mark.parametrize("threshold", (Decimal("-1"), float("inf"), float("nan")))
def test_invalid_minimum_dimension_is_rejected(threshold: Decimal | float):
    with pytest.raises(ValueError, match="minimum_dimension"):
        validate_geometry(_geometry(), minimum_dimension=threshold)


def test_pydantic_validation_input_accepts_missing_coordinates_for_reporting():
    geometry = GeometryValidationInput(x_min=0, x_max=1)

    result = validate_geometry(geometry)

    assert [error.field for error in result.errors] == [
        "y_min",
        "y_max",
        "z_min",
        "z_max",
    ]


def test_input_model_rejects_non_numeric_coordinates():
    with pytest.raises(ValidationError):
        GeometryValidationInput(x_min="not-a-coordinate")


def test_non_finite_coordinates_return_invalid_dimensions():
    result = validate_geometry(_geometry(x_min=Decimal("NaN")))

    assert result.valid is False
    assert [(error.code, error.field) for error in result.errors] == [
        ("INVALID_DIMENSIONS", "x_min")
    ]

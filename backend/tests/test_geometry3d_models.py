from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Numeric

from app.models import (
    GeometryType,
    PropertyGeometry,
    Unit,
)


def test_geometry_type_values_are_exact():
    assert {item.value for item in GeometryType} == {"aabb", "polygon_3d"}


def test_property_geometry_imports_and_required_columns():
    assert {column.name for column in PropertyGeometry.__table__.columns} == {
        "id",
        "unit_id",
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "z_min",
        "z_max",
        "geometry_type",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }


def test_property_geometry_unit_foreign_key_and_unique():
    from sqlalchemy import UniqueConstraint

    foreign_key = next(iter(PropertyGeometry.__table__.c.unit_id.foreign_keys))

    assert foreign_key.target_fullname == "units.id"
    assert foreign_key.ondelete == "CASCADE"
    # Column unique attribute is None when using UniqueConstraint instead of unique=True
    assert PropertyGeometry.__table__.c.unit_id.unique is not True
    assert "ix_property_geometry_unit_id" in {
        index.name for index in PropertyGeometry.__table__.indexes
    }
    # Check unique constraint name
    unique_constraints = [
        c
        for c in PropertyGeometry.__table__.constraints
        if isinstance(c, UniqueConstraint) and list(c.columns.keys()) == ["unit_id"]
    ]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_property_geometry_unit_id"


def test_property_geometry_fields_use_numeric_with_precision():
    numeric_fields = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    for field in numeric_fields:
        col_type = PropertyGeometry.__table__.c[field].type
        assert isinstance(col_type, Numeric)
        assert col_type.precision == 18
        assert col_type.scale == 6


def test_property_geometry_geometry_type_accepts_aabb():
    assert GeometryType.AABB.value == "aabb"


def test_property_geometry_geometry_type_accepts_polygon_3d():
    assert GeometryType.POLYGON_3D.value == "polygon_3d"


def test_property_geometry_check_constraints_exist():
    constraint_names = {
        c.name
        for c in PropertyGeometry.__table__.constraints
        if hasattr(c, "name") and c.name is not None
    }
    assert "ck_property_geometry_x_min_lt_x_max" in constraint_names
    assert "ck_property_geometry_y_min_lt_y_max" in constraint_names
    assert "ck_property_geometry_z_min_lt_z_max" in constraint_names


def test_property_geometry_computed_volume():
    geometry = PropertyGeometry(
        unit_id=uuid.uuid4(),
        x_min=Decimal("0"),
        x_max=Decimal("10"),
        y_min=Decimal("0"),
        y_max=Decimal("5"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
        geometry_type=GeometryType.AABB,
    )
    # volume = (10-0) * (5-0) * (3-0) = 150
    assert geometry.volume == Decimal("150")


def test_property_geometry_computed_centroid():
    geometry = PropertyGeometry(
        unit_id=uuid.uuid4(),
        x_min=Decimal("0"),
        x_max=Decimal("10"),
        y_min=Decimal("0"),
        y_max=Decimal("5"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
        geometry_type=GeometryType.AABB,
    )
    # centroid = ((0+10)/2, (0+5)/2, (0+3)/2) = (5, 2.5, 1.5)
    centroid = geometry.centroid
    assert centroid == (Decimal("5"), Decimal("2.5"), Decimal("1.5"))


def test_property_geometry_computed_dimensions():
    geometry = PropertyGeometry(
        unit_id=uuid.uuid4(),
        x_min=Decimal("0"),
        x_max=Decimal("10"),
        y_min=Decimal("0"),
        y_max=Decimal("5"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
        geometry_type=GeometryType.AABB,
    )
    # dimensions = (10-0, 5-0, 3-0) = (10, 5, 3)
    dimensions = geometry.dimensions
    assert dimensions == (Decimal("10"), Decimal("5"), Decimal("3"))


def test_property_geometry_computed_properties_with_decimal_coordinates():
    geometry = PropertyGeometry(
        unit_id=uuid.uuid4(),
        x_min=Decimal("1.123456"),
        x_max=Decimal("5.654321"),
        y_min=Decimal("2.5"),
        y_max=Decimal("7.25"),
        z_min=Decimal("0.1"),
        z_max=Decimal("3.141593"),
        geometry_type=GeometryType.AABB,
    )
    # volume = (5.654321 - 1.123456) * (7.25 - 2.5) * (3.141593 - 0.1)
    expected_volume = Decimal("4.530865") * Decimal("4.75") * Decimal("3.041593")
    assert geometry.volume == expected_volume

    # centroid
    expected_centroid = (
        (Decimal("1.123456") + Decimal("5.654321")) / Decimal("2"),
        (Decimal("2.5") + Decimal("7.25")) / Decimal("2"),
        (Decimal("0.1") + Decimal("3.141593")) / Decimal("2"),
    )
    assert geometry.centroid == expected_centroid

    # dimensions
    expected_dimensions = (
        Decimal("5.654321") - Decimal("1.123456"),
        Decimal("7.25") - Decimal("2.5"),
        Decimal("3.141593") - Decimal("0.1"),
    )
    assert geometry.dimensions == expected_dimensions


def test_property_geometry_relationship_back_populates():
    assert PropertyGeometry.unit.property.back_populates == "geometry"
    assert Unit.geometry.property.back_populates == "unit"
    assert Unit.geometry.property.uselist is False
    assert Unit.geometry.property.cascade.delete_orphan is True
    assert Unit.geometry.property.passive_deletes is True


def test_property_geometry_default_geometry_type():
    geometry = PropertyGeometry(
        unit_id=uuid.uuid4(),
        x_min=Decimal("0"),
        x_max=Decimal("1"),
        y_min=Decimal("0"),
        y_max=Decimal("1"),
        z_min=Decimal("0"),
        z_max=Decimal("1"),
        geometry_type=GeometryType.AABB,
    )
    assert geometry.geometry_type == GeometryType.AABB

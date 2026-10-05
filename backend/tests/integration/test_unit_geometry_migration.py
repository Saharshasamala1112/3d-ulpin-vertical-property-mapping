from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_BOUNDS = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0005_unify_unit_property_geometry.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("unify_unit_property_geometry", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_schema(connection: Connection, schema_name: str) -> None:
    connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
    connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema_name}", public')
    connection.exec_driver_sql("CREATE TYPE geometry_type AS ENUM ('aabb', 'polygon_3d')")
    connection.exec_driver_sql(
        """
        CREATE TABLE units (
            id UUID PRIMARY KEY,
            x_min NUMERIC NOT NULL, x_max NUMERIC NOT NULL,
            y_min NUMERIC NOT NULL, y_max NUMERIC NOT NULL,
            z_min NUMERIC NOT NULL, z_max NUMERIC NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE property_geometry (
            id UUID PRIMARY KEY,
            unit_id UUID NOT NULL UNIQUE REFERENCES units(id) ON DELETE CASCADE,
            x_min NUMERIC(18, 6) NOT NULL, x_max NUMERIC(18, 6) NOT NULL,
            y_min NUMERIC(18, 6) NOT NULL, y_max NUMERIC(18, 6) NOT NULL,
            z_min NUMERIC(18, 6) NOT NULL, z_max NUMERIC(18, 6) NOT NULL,
            geometry_type geometry_type NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT ck_property_geometry_x_min_lt_x_max CHECK (x_min < x_max),
            CONSTRAINT ck_property_geometry_y_min_lt_y_max CHECK (y_min < y_max),
            CONSTRAINT ck_property_geometry_z_min_lt_z_max CHECK (z_min < z_max)
        )
        """
    )


def _seed_unit(connection: Connection, unit_id: uuid.UUID, bounds: dict, timestamp) -> None:
    connection.execute(
        text(
            """
            INSERT INTO units (
                id, x_min, x_max, y_min, y_max, z_min, z_max, created_at, updated_at
            ) VALUES (
                :id, :x_min, :x_max, :y_min, :y_max, :z_min, :z_max, :created_at, :updated_at
            )
            """
        ),
        {
            "id": unit_id,
            **bounds,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )


def test_unit_bbox_migration_backfills_preserves_values_and_downgrades(
    db_session: Session,
) -> None:
    connection = db_session.connection()
    schema_name = f"unit_bbox_migration_{uuid.uuid4().hex}"
    _create_schema(connection, schema_name)

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bounds_by_unit = {
        uuid.uuid4(): {
            "x_min": Decimal("-12.123456"),
            "x_max": Decimal("10.654321"),
            "y_min": Decimal("2"),
            "y_max": Decimal("7.25"),
            "z_min": Decimal("0.1"),
            "z_max": Decimal("3.141593"),
        },
        uuid.uuid4(): {
            "x_min": Decimal("0"),
            "x_max": Decimal("5"),
            "y_min": Decimal("0"),
            "y_max": Decimal("5"),
            "z_min": Decimal("0"),
            "z_max": Decimal("3"),
        },
    }
    for unit_id, bounds in bounds_by_unit.items():
        _seed_unit(connection, unit_id, bounds, now)

    existing_unit_id, existing_bounds = next(iter(bounds_by_unit.items()))
    existing_geometry_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO property_geometry (
                id, unit_id, x_min, x_max, y_min, y_max, z_min, z_max,
                geometry_type, created_at, updated_at
            ) VALUES (
                :id, :unit_id, :x_min, :x_max, :y_min, :y_max, :z_min, :z_max,
                'aabb', :created_at, :updated_at
            )
            """
        ),
        {
            "id": existing_geometry_id,
            "unit_id": existing_unit_id,
            **existing_bounds,
            "created_at": now,
            "updated_at": now,
        },
    )

    assert connection.scalar(text("SELECT count(*) FROM units")) == len(bounds_by_unit)
    assert connection.scalar(text("SELECT count(*) FROM property_geometry")) == 1
    for unit_id, expected_bounds in bounds_by_unit.items():
        row = connection.execute(
            text("SELECT x_min, x_max, y_min, y_max, z_min, z_max FROM units WHERE id = :unit_id"),
            {"unit_id": unit_id},
        ).one()
        assert dict(zip(_BOUNDS, row, strict=True)) == expected_bounds

    migration = _load_migration()
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()

    assert not (
        set(_BOUNDS) & {column["name"] for column in inspect(connection).get_columns("units")}
    )
    assert connection.scalar(text("SELECT count(*) FROM property_geometry")) == len(bounds_by_unit)
    for unit_id, bounds in bounds_by_unit.items():
        row = connection.execute(
            text(
                """
                SELECT id, x_min, x_max, y_min, y_max, z_min, z_max,
                       created_at, updated_at
                FROM property_geometry WHERE unit_id = :unit_id
                """
            ),
            {"unit_id": unit_id},
        ).one()
        assert dict(zip(_BOUNDS, row[1:7], strict=True)) == bounds
        if unit_id == existing_unit_id:
            assert row.id == existing_geometry_id
        else:
            assert row[7] == now
            assert row[8] == now

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()

    assert set(_BOUNDS) <= {column["name"] for column in inspect(connection).get_columns("units")}
    assert connection.scalar(text("SELECT count(*) FROM units")) == len(bounds_by_unit)
    for unit_id, expected_bounds in bounds_by_unit.items():
        row = connection.execute(
            text("SELECT x_min, x_max, y_min, y_max, z_min, z_max FROM units WHERE id = :unit_id"),
            {"unit_id": unit_id},
        ).one()
        assert dict(zip(_BOUNDS, row, strict=True)) == expected_bounds

    invalid_unit_id = uuid.uuid4()
    invalid_bounds = bounds_by_unit[existing_unit_id] | {
        "x_min": Decimal("1"),
        "x_max": Decimal("1"),
    }
    _seed_unit(connection, invalid_unit_id, invalid_bounds, now)
    with Operations.context(MigrationContext.configure(connection)):
        with pytest.raises(RuntimeError, match="strict min < max"):
            migration.upgrade()

    assert set(_BOUNDS) <= {column["name"] for column in inspect(connection).get_columns("units")}
    assert connection.scalar(text("SELECT count(*) FROM property_geometry")) == len(bounds_by_unit)

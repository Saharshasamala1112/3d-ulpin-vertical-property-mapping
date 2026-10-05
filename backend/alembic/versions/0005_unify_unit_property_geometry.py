"""Make property_geometry the canonical unit bounding box.

Revision ID: 0005_unify_unit_property_geometry
Revises: 0004_create_property_geometry
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0005_unify_geometry_bounds"
down_revision: str | Sequence[str] | None = "0004_create_property_geometry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BOUNDS = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
_INSERT_GEOMETRY = sa.text(
    """
    INSERT INTO property_geometry (
        id, unit_id, x_min, x_max, y_min, y_max, z_min, z_max,
        geometry_type, created_at, updated_at
    ) VALUES (
        :id, :unit_id, :x_min, :x_max, :y_min, :y_max, :z_min, :z_max,
        'aabb', :created_at, :updated_at
    )
    """
)


def _fits_geometry_numeric(value: Decimal) -> bool:
    if not value.is_finite() or abs(value) >= Decimal("1000000000000"):
        return False
    try:
        with localcontext() as context:
            context.prec = 38
            return value == value.quantize(Decimal("0.000001"))
    except InvalidOperation:
        return False


def _sample_ids(rows: list[Any]) -> str:
    return ", ".join(str(row.unit_id) for row in rows[:10])


def upgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("LOCK TABLE units, property_geometry IN ACCESS EXCLUSIVE MODE")
    rows = connection.execute(
        sa.text(
            """
            SELECT
                u.id AS unit_id,
                u.x_min AS unit_x_min, u.x_max AS unit_x_max,
                u.y_min AS unit_y_min, u.y_max AS unit_y_max,
                u.z_min AS unit_z_min, u.z_max AS unit_z_max,
                u.created_at, u.updated_at,
                g.id AS geometry_id,
                g.x_min AS geometry_x_min, g.x_max AS geometry_x_max,
                g.y_min AS geometry_y_min, g.y_max AS geometry_y_max,
                g.z_min AS geometry_z_min, g.z_max AS geometry_z_max
            FROM units AS u
            LEFT JOIN property_geometry AS g ON g.unit_id = u.id
            ORDER BY u.id
            """
        )
    ).all()

    invalid_bounds = [
        row
        for row in rows
        if any(not row._mapping[f"unit_{field}"].is_finite() for field in _BOUNDS)
        or any(
            row._mapping[f"unit_{axis}_min"] >= row._mapping[f"unit_{axis}_max"]
            for axis in ("x", "y", "z")
        )
    ]
    if invalid_bounds:
        raise RuntimeError(
            "Cannot unify unit bounding boxes: strict min < max is required; "
            f"invalid unit IDs: {_sample_ids(invalid_bounds)}"
        )

    unrepresentable = [
        row
        for row in rows
        if any(not _fits_geometry_numeric(row._mapping[f"unit_{field}"]) for field in _BOUNDS)
    ]
    if unrepresentable:
        raise RuntimeError(
            "Cannot unify unit bounding boxes without precision loss; "
            "property_geometry supports 18 digits with 6 decimal places. "
            f"Unrepresentable unit IDs: {_sample_ids(unrepresentable)}"
        )

    conflicts = [
        row
        for row in rows
        if row.geometry_id is not None
        and any(
            row._mapping[f"unit_{field}"] != row._mapping[f"geometry_{field}"] for field in _BOUNDS
        )
    ]
    if conflicts:
        raise RuntimeError(
            "Cannot unify unit bounding boxes because existing property_geometry values "
            "conflict with units; reconcile these records before upgrading. "
            f"Conflicting unit IDs: {_sample_ids(conflicts)}"
        )

    missing = [row for row in rows if row.geometry_id is None]
    for offset in range(0, len(missing), 500):
        batch = missing[offset : offset + 500]
        connection.execute(
            _INSERT_GEOMETRY,
            [
                {
                    "id": uuid.uuid4(),
                    "unit_id": row.unit_id,
                    **{field: row._mapping[f"unit_{field}"] for field in _BOUNDS},
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in batch
            ],
        )

    unit_count = connection.scalar(sa.text("SELECT count(*) FROM units"))
    geometry_count = connection.scalar(sa.text("SELECT count(*) FROM property_geometry"))
    mismatched_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM units AS u
            LEFT JOIN property_geometry AS g ON g.unit_id = u.id
            WHERE g.id IS NULL
               OR u.x_min != g.x_min OR u.x_max != g.x_max
               OR u.y_min != g.y_min OR u.y_max != g.y_max
               OR u.z_min != g.z_min OR u.z_max != g.z_max
            """
        )
    )
    if unit_count != geometry_count or mismatched_count:
        raise RuntimeError(
            "Bounding-box backfill verification failed: "
            f"{unit_count} units, {geometry_count} geometries, {mismatched_count} mismatches"
        )

    for field in _BOUNDS:
        op.drop_column("units", field)


def downgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("LOCK TABLE units, property_geometry IN ACCESS EXCLUSIVE MODE")
    for field in _BOUNDS:
        op.add_column("units", sa.Column(field, sa.Numeric(), nullable=True))

    missing_geometry = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM units AS u
            LEFT JOIN property_geometry AS g ON g.unit_id = u.id
            WHERE g.id IS NULL
            """
        )
    )
    if missing_geometry:
        raise RuntimeError(
            "Cannot restore unit bounding-box columns: "
            f"{missing_geometry} unit(s) have no property_geometry row"
        )

    connection.execute(
        sa.text(
            """
            UPDATE units AS u
            SET x_min = g.x_min, x_max = g.x_max,
                y_min = g.y_min, y_max = g.y_max,
                z_min = g.z_min, z_max = g.z_max
            FROM property_geometry AS g
            WHERE g.unit_id = u.id
            """
        )
    )

    for field in _BOUNDS:
        op.alter_column("units", field, existing_type=sa.Numeric(), nullable=False)

    null_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM units
            WHERE x_min IS NULL OR x_max IS NULL
               OR y_min IS NULL OR y_max IS NULL
               OR z_min IS NULL OR z_max IS NULL
            """
        )
    )
    if null_count:
        raise RuntimeError(f"Bounding-box downgrade verification failed for {null_count} unit(s)")

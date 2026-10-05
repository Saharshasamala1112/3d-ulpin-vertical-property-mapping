"""Create property_geometry table.

Revision ID: 0004_create_property_geometry
Revises: 0003_create_floors_and_units
Create Date: 2026-09-26 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_create_property_geometry"
down_revision: str | Sequence[str] | None = "0003_create_floors_and_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    geometry_type = sa.Enum(
        "aabb",
        "polygon_3d",
        name="geometry_type",
        create_type=True,
    )

    op.create_table(
        "property_geometry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("x_min", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("x_max", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("y_min", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("y_max", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("z_min", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("z_max", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("geometry_type", geometry_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", name="uq_property_geometry_unit_id"),
        sa.CheckConstraint("x_min < x_max", name="ck_property_geometry_x_min_lt_x_max"),
        sa.CheckConstraint("y_min < y_max", name="ck_property_geometry_y_min_lt_y_max"),
        sa.CheckConstraint("z_min < z_max", name="ck_property_geometry_z_min_lt_z_max"),
    )
    op.create_index("ix_property_geometry_unit_id", "property_geometry", ["unit_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_property_geometry_unit_id", table_name="property_geometry")
    op.drop_table("property_geometry")

    geometry_type = sa.Enum("aabb", "polygon_3d", name="geometry_type")
    geometry_type.drop(op.get_bind(), checkfirst=True)

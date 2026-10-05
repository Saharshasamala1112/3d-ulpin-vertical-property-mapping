"""Create floors and units tables.

Revision ID: 0003_create_floors_and_units
Revises: 0002_create_buildings
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_create_floors_and_units"
down_revision: str | Sequence[str] | None = "0002_create_buildings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    floor_type = sa.Enum(
        "basement",
        "ground",
        "typical",
        "penthouse",
        "rooftop",
        name="floor_type",
        create_type=True,
    )
    unit_type = sa.Enum(
        "residential",
        "commercial",
        "parking",
        "storage",
        "common_area",
        name="unit_type",
        create_type=True,
    )
    unit_status = sa.Enum(
        "planned",
        "active",
        "sold",
        "leased",
        "archived",
        name="unit_status",
        create_type=True,
    )

    op.create_table(
        "floors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("building_id", sa.Uuid(), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False),
        sa.Column("level_name", sa.String(length=255), nullable=True),
        sa.Column("floor_type", floor_type, nullable=False),
        sa.Column("elevation_min", sa.Numeric(), nullable=False),
        sa.Column("elevation_max", sa.Numeric(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_floors_building_id", "floors", ["building_id"], unique=False)

    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("floor_id", sa.Uuid(), nullable=False),
        sa.Column("unit_identifier", sa.String(length=255), nullable=False),
        sa.Column("unit_type", unit_type, nullable=False),
        sa.Column("area_sqm", sa.Numeric(), nullable=False),
        sa.Column("x_min", sa.Numeric(), nullable=False),
        sa.Column("x_max", sa.Numeric(), nullable=False),
        sa.Column("y_min", sa.Numeric(), nullable=False),
        sa.Column("y_max", sa.Numeric(), nullable=False),
        sa.Column("z_min", sa.Numeric(), nullable=False),
        sa.Column("z_max", sa.Numeric(), nullable=False),
        sa.Column("status", unit_status, nullable=False),
        sa.Column("vdc_code", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["floor_id"], ["floors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_units_floor_id", "units", ["floor_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_units_floor_id", table_name="units")
    op.drop_table("units")
    op.drop_index("ix_floors_building_id", table_name="floors")
    op.drop_table("floors")

    sa.Enum(name="unit_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="unit_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="floor_type").drop(op.get_bind(), checkfirst=True)

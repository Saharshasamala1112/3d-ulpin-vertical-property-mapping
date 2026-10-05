"""Create buildings table.

Revision ID: 0002_create_buildings
Revises: d57017b4753a
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

revision: str = "0002_create_buildings"
down_revision: str | Sequence[str] | None = "d57017b4753a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    building_type = sa.Enum(
        "residential",
        "commercial",
        "mixed_use",
        "industrial",
        "institutional",
        name="building_type",
        create_type=True,
    )
    construction_status = sa.Enum(
        "planned",
        "under_construction",
        "completed",
        "demolished",
        name="construction_status",
        create_type=True,
    )
    op.create_table(
        "buildings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parcel_id", sa.Uuid(), nullable=False),
        sa.Column("building_identifier", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("building_type", building_type, nullable=False),
        sa.Column("construction_status", construction_status, nullable=False),
        sa.Column(
            "footprint_geometry",
            geoalchemy2.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buildings_parcel_id", "buildings", ["parcel_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_buildings_parcel_id", table_name="buildings")
    op.drop_table("buildings")

    sa.Enum(name="construction_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="building_type").drop(op.get_bind(), checkfirst=True)

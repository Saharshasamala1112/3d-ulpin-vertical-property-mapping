"""Create owners and effective-dated ownership interests.

Revision ID: 0004_create_ownership
Revises: 0003_create_floors_and_units
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_create_ownership"
down_revision: str | Sequence[str] | None = "0003_create_floors_and_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `kind` and `status` are native PostgreSQL enums, matching every other enum
# column in this schema (building_type, unit_type, parcel_status, ...). A
# VARCHAR plus `CHECK (x IN (...))` was rejected here because PostgreSQL
# rewrites such a check to `x = ANY (ARRAY[...])` on storage, so the live
# constraint text can never match the model metadata.
#
# `create_type=False` keeps Alembic from emitting a second CREATE TYPE: the
# types are created and dropped explicitly below.
OWNER_KIND = postgresql.ENUM(
    "individual",
    "organization",
    name="owner_kind",
    create_type=False,
)
OWNERSHIP_STATUS = postgresql.ENUM(
    "active",
    "transferred",
    "revoked",
    name="ownership_status",
    create_type=False,
)


def upgrade() -> None:
    OWNER_KIND.create(op.get_bind(), checkfirst=True)
    OWNERSHIP_STATUS.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "owners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", OWNER_KIND, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=True),
        sa.Column("contact_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # `created_at`/`updated_at` deliberately carry no server default: the
        # `BaseModel` supplies them Python-side (`default=`), and the other
        # tables in this schema are created the same way.
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ownership_interests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("parcel_id", sa.Uuid(), nullable=True),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("share_basis_points", sa.SmallInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", OWNERSHIP_STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            # Spelled the way PostgreSQL stores these expressions: it drops the
            # redundant parentheses and rewrites BETWEEN as two comparisons,
            # so any other spelling reflects back as different constraint text.
            "parcel_id IS NOT NULL AND unit_id IS NULL "
            "OR parcel_id IS NULL AND unit_id IS NOT NULL",
            name="ck_ownership_interests_exactly_one_subject",
        ),
        sa.CheckConstraint(
            "share_basis_points >= 1 AND share_basis_points <= 10000",
            name="ck_ownership_interests_share_basis_points",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_ownership_interests_valid_interval",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ownership_interests_owner_id",
        "ownership_interests",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_ownership_interests_parcel_effective",
        "ownership_interests",
        ["parcel_id", "valid_from", "valid_to"],
        unique=False,
        postgresql_where=sa.text("parcel_id IS NOT NULL"),
    )
    op.create_index(
        "ix_ownership_interests_unit_effective",
        "ownership_interests",
        ["unit_id", "valid_from", "valid_to"],
        unique=False,
        postgresql_where=sa.text("unit_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_ownership_interests_unit_effective", table_name="ownership_interests")
    op.drop_index("ix_ownership_interests_parcel_effective", table_name="ownership_interests")
    op.drop_index("ix_ownership_interests_owner_id", table_name="ownership_interests")
    op.drop_table("ownership_interests")
    op.drop_table("owners")
    OWNERSHIP_STATUS.drop(op.get_bind(), checkfirst=True)
    OWNER_KIND.drop(op.get_bind(), checkfirst=True)
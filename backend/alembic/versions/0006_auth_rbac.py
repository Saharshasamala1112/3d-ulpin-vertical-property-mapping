"""Add users, login throttling, password resets, and audit columns.

Implements the persistence half of Feature 39 (authentication + RBAC):

* ``user_role`` enum and ``users`` table backing DB-persisted accounts with a
  ``reader``/``editor``/``admin`` role.
* ``login_attempts`` — per-email and per-IP failed-login counters that survive
  a process restart.
* ``password_reset_tokens`` — single-use, expiring reset tokens stored only as
  SHA-256 digests.
* ``created_by`` / ``updated_by`` audit columns on the core cadastral tables
  (parcels, buildings, floors, units, ulpins, property_geometry). Plain UUIDs,
  no foreign keys: the audit trail must outlive the user account.

Revision ID: 0006_auth_rbac
Revises: 0005_unify_geometry_bounds
Create Date: 2026-10-01 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_auth_rbac"
down_revision: str | Sequence[str] | None = "0005_unify_geometry_bounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tables that gain created_by/updated_by audit columns.
AUDIT_TABLES = (
    "parcels",
    "buildings",
    "floors",
    "units",
    "ulpins",
    "property_geometry",
)


def upgrade() -> None:
    user_role = sa.Enum(
        "reader",
        "editor",
        "admin",
        name="user_role",
        create_type=True,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=400), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("first_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject"),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )

    for table_name in AUDIT_TABLES:
        op.add_column(table_name, sa.Column("created_by", sa.Uuid(), nullable=True))
        op.add_column(table_name, sa.Column("updated_by", sa.Uuid(), nullable=True))


def downgrade() -> None:
    for table_name in reversed(AUDIT_TABLES):
        op.drop_column(table_name, "updated_by")
        op.drop_column(table_name, "created_by")

    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("login_attempts")
    op.drop_table("users")

    user_role = sa.Enum("reader", "editor", "admin", name="user_role")
    user_role.drop(op.get_bind(), checkfirst=True)

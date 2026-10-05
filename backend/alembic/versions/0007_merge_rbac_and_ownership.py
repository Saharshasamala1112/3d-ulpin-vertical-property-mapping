"""Merge the auth/RBAC chain into the ownership and geometry chain.

Revision ID: 0007_merge_rbac_and_ownership
Revises: 0006_auth_rbac, 0006_merge_ownership_geometry
"""

from collections.abc import Sequence

revision: str = "0007_merge_rbac_and_ownership"
down_revision: str | Sequence[str] | None = (
    "0006_auth_rbac",
    "0006_merge_ownership_geometry",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: both parents already applied their own schema changes.

    ``0006_auth_rbac`` creates ``users``, ``login_attempts`` and
    ``password_reset_tokens`` and adds the nullable ``created_by`` /
    ``updated_by`` audit columns to parcels, buildings, floors, units, ulpins
    and property_geometry. ``0006_merge_ownership_geometry`` is itself an empty
    merge that only reunites the ownership chain with the geometry chain.

    Neither parent creates, drops or alters a table, column, constraint or
    index that the other one touches, so there is nothing to reconcile and this
    revision exists purely to leave alembic with a single head.
    """


def downgrade() -> None:
    """No-op: this merge carries no schema change of its own."""
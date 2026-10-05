"""Merge the ownership and geometry-unification branches.

Both ``0004_create_ownership`` (epic/ownership-governance) and
``0005_unify_geometry_bounds`` (develop, via ``0004_create_property_geometry``)
branched off ``0003_create_floors_and_units``, so the merged tree carries two
revision heads. This empty merge revision joins them into a single head again;
it performs no schema work of its own because the two branches touch disjoint
tables (``owners`` / ``ownership_interests`` versus ``property_geometry`` and
``units``).

Revision ID: 0006_merge_ownership_geometry
Revises: 0004_create_ownership, 0005_unify_geometry_bounds

The revision id must stay within ``alembic_version.version_num``'s VARCHAR(32).
"""

from collections.abc import Sequence

revision: str = "0006_merge_ownership_geometry"
down_revision: str | Sequence[str] | None = (
    "0004_create_ownership",
    "0005_unify_geometry_bounds",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: the two parents already applied their own schema changes."""


def downgrade() -> None:
    """No-op: downgrading simply drops back to the two branch heads."""
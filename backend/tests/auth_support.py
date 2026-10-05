"""Shared helpers for role-aware tests (Feature 39 — auth + RBAC).

Mints bearer tokens for the three fixed seed users that
``tests/conftest.py`` installs into the per-test in-memory auth database.
Token minting is pure (JWT signing only), so helpers here can be used at
import time without a database.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from app.core.security import create_token, hash_password

#: Fixed ids for the seeded role users, so tests can assert on audit columns.
READER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-0000000000f2")
ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000f3")

SEED_EMAILS = {
    "reader": "reader@example.com",
    "editor": "editor@example.com",
    "admin": "admin@example.com",
}

SEED_FULL_NAMES = {
    "reader": "Reader Tester",
    "editor": "Editor Tester",
    "admin": "Admin Tester",
}

#: Password shared by all seeded users. Only ever used against test databases.
SEED_PASSWORD = "geosix-rbac-test-password"

_ROLE_IDS = {
    "reader": READER_ID,
    "editor": EDITOR_ID,
    "admin": ADMIN_ID,
}


def user_id_for(role: str) -> uuid.UUID:
    """Return the fixed id of the seeded user holding ``role``."""
    return _ROLE_IDS[role]


def bearer_headers(role: str) -> dict[str, str]:
    """Authorization headers carrying a valid access token for ``role``."""
    token = create_token(str(_ROLE_IDS[role]), "access")
    return {"Authorization": f"Bearer {token}"}


@lru_cache(maxsize=1)
def seed_password_hash() -> str:
    """bcrypt hash of :data:`SEED_PASSWORD`, computed once per test session.

    Hashing is the slow part of seeding three users per test; caching keeps
    the per-test fixture cheap while still exercising real bcrypt.
    """
    return hash_password(SEED_PASSWORD)

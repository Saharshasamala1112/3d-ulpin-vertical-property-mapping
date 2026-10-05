"""Shared pytest configuration for the whole backend test suite.

Scope notes
-----------
Anything that needs PostGIS lives in ``tests/integration/conftest.py`` so that
the fast unit tests keep working on machines without a PostGIS instance.

The one sanctioned exception is the *authentication* database: since Feature 39
moved users, login throttling, and password-reset tokens into SQL, every API
request resolves the bearer user through the ORM. The fixture below therefore
serves those three tables from a private in-memory SQLite database for each
test, seeded with the fixed reader/editor/admin users that
``tests/auth_support.py`` mints tokens for. Data routers stay database-free in
unit tests because their service functions are mocked.

Bcrypt cost is also handled here. Hashing dominates the runtime of the
existing authentication tests (roughly 10s at the production cost factor), so
the test session lowers it. Authentication *assertions* are untouched: passwords
are still really hashed with bcrypt and really verified, only with a cheaper
cost factor. Production keeps the normal value from
``app.core.config.Settings.bcrypt_rounds``.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, settings
from app.core.database import Base, get_db
from app.core.security import pwd_context

#: bcrypt's minimum accepted cost factor.
TEST_BCRYPT_ROUNDS = 4


@pytest.fixture(scope="session", autouse=True)
def fast_bcrypt_for_tests():
    """Lower the bcrypt cost factor for the duration of the test session.

    Yields so pytest reports a clear teardown boundary, and restores both the
    settings value and the live ``CryptContext`` afterwards.
    """
    original_rounds = settings.bcrypt_rounds
    settings.bcrypt_rounds = TEST_BCRYPT_ROUNDS
    pwd_context.update(bcrypt__rounds=TEST_BCRYPT_ROUNDS)
    try:
        yield
    finally:
        pwd_context.update(bcrypt__rounds=original_rounds)
        settings.bcrypt_rounds = original_rounds


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Surface the effective test environment in the pytest header."""
    return [f"bcrypt rounds (test session): {settings.bcrypt_rounds}"]


@pytest.fixture(autouse=True)
def sqlite_auth_database() -> Generator[sessionmaker, None, None]:
    """Back ``get_db`` with a private in-memory SQLite auth database.

    Creates only the tables the request path itself needs (``users``,
    ``login_attempts``, ``password_reset_tokens``) and seeds the three fixed
    role users from ``tests/auth_support.py``. Fresh per test, so failed-login
    counters and single-use reset tokens never leak between tests, and tests
    that register users through the API always start from a clean slate.

    Data tables (parcels, ...) are intentionally absent: unit tests mock the
    service layer, and any request that reaches an unmocked data query would
    fail loudly here rather than silently touching a real database.

    Yields the session factory so tests that must inspect or age throttle/reset
    rows (locked_until in the past, token expiry) can open their own session
    against the same database.
    """
    from app.main import app
    from app.models.login_attempt import LoginAttempt  # noqa: F401  (registers the table)
    from app.models.password_reset_token import PasswordResetToken  # noqa: F401
    from app.models.user import User, UserRole
    from tests.auth_support import (
        SEED_EMAILS,
        SEED_FULL_NAMES,
        seed_password_hash,
        user_id_for,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables["users"],
            Base.metadata.tables["login_attempts"],
            Base.metadata.tables["password_reset_tokens"],
        ],
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    seed_session = session_factory()
    try:
        for role in ("reader", "editor", "admin"):
            seed_session.add(
                User(
                    id=user_id_for(role),
                    email=SEED_EMAILS[role],
                    password_hash=seed_password_hash(),
                    full_name=SEED_FULL_NAMES[role],
                    is_active=True,
                    role=UserRole(role),
                )
            )
        seed_session.commit()
    finally:
        seed_session.close()

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.fixture
def production_settings() -> Settings:
    """A ``Settings`` instance that ignores any ambient environment overrides.

    Useful for asserting that shipped defaults (e.g. the production bcrypt cost)
    are what we intend, regardless of the developer's local ``.env``.
    """
    return Settings(_env_file=None, bcrypt_rounds=12)

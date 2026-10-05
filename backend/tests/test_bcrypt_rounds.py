"""bcrypt cost configuration and hashing correctness.

The test session lowers the bcrypt cost factor in ``tests/conftest.py`` to keep
the suite fast. These tests make sure that optimization is a *performance* choice
only: hashing is still real bcrypt, verification is still real, and the shipped
production default is still the normal value.
"""

from __future__ import annotations

from app.core.config import Settings, settings
from app.core.security import hash_password, pwd_context, verify_password


def test_production_default_bcrypt_rounds_is_unchanged() -> None:
    """The shipped default must stay at the normal cost factor."""
    assert Settings.model_fields["bcrypt_rounds"].default == 12


def test_test_session_uses_a_cheaper_cost_factor() -> None:
    """The suite lowers the cost factor so authentication tests stay fast."""
    assert settings.bcrypt_rounds == 4
    assert settings.bcrypt_rounds < 12


def test_hash_password_produces_a_real_bcrypt_hash() -> None:
    """Hashing is genuine bcrypt, not a stub."""
    hashed = hash_password("correct horse battery staple")

    assert hashed.startswith("$2")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_the_correct_password() -> None:
    """Verification succeeds for the right password."""
    hashed = hash_password("s3cret-passphrase")

    assert verify_password("s3cret-passphrase", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    """Verification fails for a wrong password."""
    hashed = hash_password("s3cret-passphrase")

    assert verify_password("wrong-passphrase", hashed) is False


def test_hashes_are_salted_and_unique() -> None:
    """Two hashes of the same password differ, so plaintext is not recoverable."""
    first = hash_password("repeated-password")
    second = hash_password("repeated-password")

    assert first != second
    assert verify_password("repeated-password", first) is True
    assert verify_password("repeated-password", second) is True


def test_hash_matches_the_live_crypt_context() -> None:
    """hash_password uses the same live context the app configured."""
    hashed = hash_password("context-check")

    assert pwd_context.verify("context-check", hashed)
    assert not pwd_context.verify("not-the-password", hashed)

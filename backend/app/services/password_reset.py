"""Functional password-reset flow (issue #39).

``request_password_reset`` issues a single-use, expiring token for a known
address and hands the emailed link to :mod:`app.services.email`. Unknown
addresses are indistinguishable from slow ones: no token is created and the
caller still reports success, so the endpoint cannot be used to enumerate
accounts.

Only the SHA-256 digest of the token is stored; the plaintext lives in the
email and is never persisted or logged.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.login_attempt import LoginAttempt
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email import send_password_reset_email
from app.services.login_throttle import email_key

logger = logging.getLogger("geosix.auth")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> bool:
    """Issue a reset token and email the link. Returns True when dispatched.

    The return value is only about dispatch; the API response must not depend
    on it or on whether the address exists.
    """
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        logger.info("Password reset requested for unknown address")
        return False

    # A new request supersedes any still-outstanding token for this account.
    db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )

    token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=expires_at,
        )
    )
    db.commit()

    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"
    return send_password_reset_email(user.email, reset_url)


def reset_password(db: Session, token: str, new_password: str) -> None:
    """Consume ``token`` and set the account password.

    Raises ``ValueError`` with a distinct message for unknown, already-used,
    and expired tokens (the router maps each to a 400).
    """
    now = _utcnow()
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))
    )
    if row is None:
        raise ValueError("Invalid reset token")
    if row.used_at is not None:
        raise ValueError("Reset token has already been used")
    if _as_utc(row.expires_at) <= now:
        raise ValueError("Reset token has expired")

    user = db.get(User, row.user_id)
    if user is None:
        raise ValueError("Invalid reset token")

    user.password_hash = hash_password(new_password)
    row.used_at = now
    # A password change also releases any login lockout on this address.
    db.execute(delete(LoginAttempt).where(LoginAttempt.subject == email_key(user.email)))
    db.commit()
    logger.info("Password reset completed for user %s", user.id)

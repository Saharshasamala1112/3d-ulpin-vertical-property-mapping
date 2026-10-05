"""Login throttling backed by the ``login_attempts`` table.

Two throttle keys are tracked per attempt: ``email:<address>`` (protects one
account from password spraying) and ``ip:<address>`` (protects the service from
a single hostile source hammering many accounts). State lives in the database,
so a lockout survives a process restart.

A lock lasts ``settings.login_lockout_minutes``; once it expires the counter
resets on the next check and the subject may retry immediately.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.login_attempt import LoginAttempt


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def email_key(email: str) -> str:
    """Throttle key for an email address."""
    return f"email:{email.strip().lower()}"


def ip_key(ip_address: str) -> str:
    """Throttle key for a client IP address."""
    return f"ip:{ip_address}"


def locked_until(db: Session, subject: str, now: datetime | None = None) -> datetime | None:
    """Return when ``subject``'s lock expires, or ``None`` when not locked.

    An expired lock is cleared as a side effect so the next attempt starts
    with a fresh counter.
    """
    now = now or _utcnow()
    row = db.scalar(select(LoginAttempt).where(LoginAttempt.subject == subject))
    if row is None or row.locked_until is None:
        return None
    locked_until = _as_utc(row.locked_until)
    if locked_until > now:
        return locked_until
    row.failure_count = 0
    row.locked_until = None
    row.first_failure_at = None
    db.commit()
    return None


def record_failure(db: Session, subject: str, now: datetime | None = None) -> None:
    """Record one failed attempt for ``subject`` and apply lockout if due."""
    now = now or _utcnow()
    row = db.scalar(select(LoginAttempt).where(LoginAttempt.subject == subject))
    if row is None:
        row = LoginAttempt(
            subject=subject,
            failure_count=0,
            first_failure_at=now,
            last_failure_at=now,
        )
        db.add(row)
    elif row.locked_until is not None and _as_utc(row.locked_until) <= now:
        # A previous window elapsed without the counter being consumed.
        row.failure_count = 0
        row.locked_until = None
        row.first_failure_at = now

    row.failure_count += 1
    row.last_failure_at = now
    if row.first_failure_at is None:
        row.first_failure_at = now
    if row.failure_count >= settings.login_max_attempts:
        row.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
    db.commit()


def clear_failures(db: Session, subjects: list[str]) -> None:
    """Drop throttle state for ``subjects`` (called after a successful login)."""
    if not subjects:
        return
    db.execute(delete(LoginAttempt).where(LoginAttempt.subject.in_(subjects)))
    db.commit()

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger("geosix.auth")


def _as_utc_string(value) -> str:
    """Render a datetime (or pre-formatted string) as an ISO-8601 string."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def get_user_response(user: User) -> UserResponse:
    """Convert an ORM :class:`User` to the public :class:`UserResponse`."""
    role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role=role.value,
        created_at=_as_utc_string(user.created_at),
        updated_at=_as_utc_string(user.updated_at),
    )


def _find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def register_user(db: Session, data: UserCreate) -> UserResponse:
    """Register a new reader-role user. Raises ValueError on duplicate email."""
    if _find_user_by_email(db, data.email) is not None:
        raise ValueError("Email already registered")

    user = User(
        email=data.email.strip(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
        role=UserRole.READER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered: %s", user.id)
    return get_user_response(user)


def authenticate_user(db: Session, data: UserLogin) -> TokenResponse:
    """Authenticate user and return tokens. Raises ValueError on failure.

    Throttling (lockouts, failure counters) is applied by the caller — the API
    layer — so this function stays a pure credential check.
    """
    user = _find_user_by_email(db, data.email)
    if user is None or not verify_password(data.password, user.password_hash):
        raise ValueError("Invalid email or password")

    access_token = create_token(str(user.id), "access")
    refresh_token = create_token(str(user.id), "refresh")
    logger.info("User authenticated: %s", user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
    """Exchange a valid refresh token for new tokens. Raises ValueError on failure."""
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise ValueError("Invalid or expired refresh token")

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid or expired refresh token") from None

    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    access_token = create_token(str(user.id), "access")
    new_refresh_token = create_token(str(user.id), "refresh")
    logger.info("Tokens refreshed for user: %s", user.id)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)

from __future__ import annotations

import logging
import uuid

from app.core.security import create_token, hash_password, verify_password
from app.models.user import UserModel, create_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger("geosix.auth")


def register_user(data: UserCreate) -> UserResponse:
    """Register a new user. Raises ValueError on duplicate email."""
    if UserModel.email_exists(data.email):
        raise ValueError("Email already registered")

    user = create_user(
        user_id=str(uuid.uuid4()),
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    logger.info("User registered: %s", user["id"])
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )


def authenticate_user(data: UserLogin) -> TokenResponse:
    """Authenticate user and return tokens. Raises ValueError on failure."""
    user = UserModel.get_by_email(data.email)
    if user is None or not verify_password(data.password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    access_token = create_token(user["id"], "access")
    refresh_token = create_token(user["id"], "refresh")
    logger.info("User authenticated: %s", user["id"])
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def refresh_tokens(refresh_token: str) -> TokenResponse:
    """Exchange a valid refresh token for new tokens. Raises ValueError on failure."""
    from app.core.security import decode_token

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise ValueError("Invalid or expired refresh token")

    user = UserModel.get_by_id(payload["sub"])
    if user is None:
        raise ValueError("User not found")

    access_token = create_token(user["id"], "access")
    new_refresh_token = create_token(user["id"], "refresh")
    logger.info("Tokens refreshed for user: %s", user["id"])
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


def get_user_response(user: dict) -> UserResponse:
    """Convert a user dict to a UserResponse schema."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser
from app.core.security import create_token, hash_password, verify_password
from app.models.user import UserModel, create_user
from app.schemas.auth import (
    ErrorResponse,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def register(body: UserCreate):
    if UserModel.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "EMAIL_EXISTS", "message": "Email already registered"}},
        )
    user = create_user(
        user_id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
)
async def login(body: UserLogin):
    user = UserModel.get_by_email(body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Invalid email or password",
                }
            },
        )
    access_token = create_token(user["id"], "access")
    refresh_token = create_token(user["id"], "refresh")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
async def refresh_token(body: RefreshRequest):
    from app.core.security import decode_token

    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "Invalid or expired refresh token",
                }
            },
        )
    user = UserModel.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
        )
    access_token = create_token(user["id"], "access")
    refresh_token = create_token(user["id"], "refresh")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(current_user: CurrentUser):
    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_me(current_user: CurrentUser):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
        updated_at=current_user["updated_at"],
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
async def forgot_password(email: str):
    return MessageResponse(message="If the email exists, a reset link has been sent")

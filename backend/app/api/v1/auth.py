from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DatabaseSession, require_admin
from app.models.user import User, UserRole
from app.schemas.auth import (
    ErrorResponse,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RoleUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services import login_throttle, password_reset
from app.services.auth import (
    authenticate_user,
    get_user_response,
    refresh_tokens,
    register_user,
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
async def register(body: UserCreate, db: DatabaseSession):
    try:
        return register_user(db, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"model": ErrorResponse, "description": "Too many failed attempts"},
    },
)
async def login(body: UserLogin, request: Request, db: DatabaseSession):
    client_ip = request.client.host if request.client else "unknown"
    subjects = [login_throttle.email_key(body.email), login_throttle.ip_key(client_ip)]

    for subject in subjects:
        locked = login_throttle.locked_until(db, subject)
        if locked is not None:
            retry_after = max(int((locked - login_throttle._utcnow()).total_seconds()), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "TOO_MANY_ATTEMPTS",
                        "message": "Too many failed login attempts. Please try again later.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

    try:
        tokens = authenticate_user(db, body)
    except ValueError as e:
        for subject in subjects:
            login_throttle.record_failure(db, subject)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_FAILED", "message": str(e)}},
        )

    login_throttle.clear_failures(db, subjects)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
async def refresh_token(body: RefreshRequest, db: DatabaseSession):
    try:
        return refresh_tokens(db, body.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_REFRESH_TOKEN", "message": str(e)}},
        )


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
    return get_user_response(current_user)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
async def forgot_password(body: PasswordResetRequest, db: DatabaseSession):
    """Always reports success — the response must not reveal account existence."""
    password_reset.request_password_reset(db, body.email)
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid, used, or expired token"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def reset_password(body: PasswordResetConfirm, db: DatabaseSession):
    try:
        password_reset.reset_password(db, body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_RESET_TOKEN", "message": str(e)}},
        )
    return MessageResponse(message="Password has been reset successfully")


@router.get(
    "/users",
    response_model=list[UserResponse],
    dependencies=[Depends(require_admin)],
    responses={
        403: {"model": ErrorResponse, "description": "Admin role required"},
    },
)
async def list_users(db: DatabaseSession):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [get_user_response(user) for user in users]


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(require_admin)],
    responses={
        403: {"model": ErrorResponse, "description": "Admin role required"},
        404: {"model": ErrorResponse, "description": "User not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def assign_role(user_id: uuid.UUID, body: RoleUpdate, db: DatabaseSession):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.role = UserRole(body.role)
    db.commit()
    db.refresh(user)
    return get_user_response(user)

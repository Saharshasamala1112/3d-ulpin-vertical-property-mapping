from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

#: Role names accepted by the admin role-assignment endpoint.
RoleName = Literal["reader", "editor", "admin"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    role: str
    created_at: str
    updated_at: str


class RoleUpdate(BaseModel):
    role: RoleName


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    type: str  # "access" or "refresh"
    exp: int


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ErrorDetail(BaseModel):
    code: str
    message: str

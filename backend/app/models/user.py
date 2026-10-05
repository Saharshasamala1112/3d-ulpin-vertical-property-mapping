from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserRole(str, PyEnum):
    """Role assigned to a user. Determines the permission matrix tier."""

    READER = "reader"
    EDITOR = "editor"
    ADMIN = "admin"


class User(BaseModel):
    """A registered user account persisted in the ``users`` table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=UserRole.READER,
    )

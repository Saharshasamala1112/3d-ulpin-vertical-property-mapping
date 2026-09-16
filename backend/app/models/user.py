from __future__ import annotations

from datetime import datetime, timezone


class UserModel:
    """In-memory user storage for development. Replace with database in production."""

    _users: dict[str, dict] = {}
    _by_email: dict[str, str] = {}

    @classmethod
    def create(cls, user: dict) -> dict:
        cls._users[user["id"]] = user
        cls._by_email[user["email"]] = user["id"]
        return user

    @classmethod
    def get_by_id(cls, user_id: str) -> dict | None:
        return cls._users.get(user_id)

    @classmethod
    def get_by_email(cls, email: str) -> dict | None:
        user_id = cls._by_email.get(email)
        if user_id:
            return cls._users.get(user_id)
        return None

    @classmethod
    def email_exists(cls, email: str) -> bool:
        return email in cls._by_email


def create_user(
    user_id: str,
    email: str,
    password_hash: str,
    full_name: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": user_id,
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    return UserModel.create(user)

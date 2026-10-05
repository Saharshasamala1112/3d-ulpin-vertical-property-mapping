from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class LoginAttempt(BaseModel):
    """Failed-login tracking row for one throttle key.

    The key (``subject``) is either ``email:<address>`` or ``ip:<address>`` so
    that throttling works per-username *and* per-source-IP. State lives in the
    database so a lockout survives a process restart.
    """

    __tablename__ = "login_attempts"

    subject: Mapped[str] = mapped_column(String(400), unique=True, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

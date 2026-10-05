"""Audit-column population for API-driven writes.

The permission dependencies in :mod:`app.core.dependencies` stash the
authenticated user's id on the request session (``session.info``). This module
listens for flushes and stamps ``created_by`` / ``updated_by`` on any model
that declares those columns (see :class:`app.models.audit.AuditColumns`).

Services never change: they keep writing plain ORM objects, and attribution
happens transparently. Sessions without a stamp (factories, migrations,
scripts) leave the columns ``NULL``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

#: Key under which the current user id is stored on ``session.info``.
AUDIT_USER_KEY = "geosix.current_user_id"


def stamp_current_user(session: Session, user_id: uuid.UUID) -> None:
    """Record the authenticated user on the session for audit stamping."""
    session.info[AUDIT_USER_KEY] = user_id


def current_stamped_user(session: Session) -> uuid.UUID | None:
    """Return the user id stamped on the session, if any."""
    value = getattr(session, "info", {}).get(AUDIT_USER_KEY)
    return value if isinstance(value, uuid.UUID) else None


@event.listens_for(Session, "before_flush")
def _stamp_audit_columns(session: Session, flush_context, instances) -> None:
    user_id = current_stamped_user(session)
    if user_id is None:
        return

    for target in session.new:
        if hasattr(target, "created_by"):
            target.created_by = user_id
        if hasattr(target, "updated_by"):
            target.updated_by = user_id

    for target in session.dirty:
        if hasattr(target, "updated_by"):
            target.updated_by = user_id

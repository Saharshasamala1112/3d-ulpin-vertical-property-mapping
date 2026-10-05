from __future__ import annotations

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column


class AuditColumns:
    """``created_by`` / ``updated_by`` columns for core cadastral tables.

    Deliberately *not* foreign keys: the audit trail must survive deletion of
    the user account that produced it, and keeping them plain UUIDs avoids
    coupling the lifecycle of user rows to historical cadastral records.

    Population is handled by the ``before_flush`` listener in
    :mod:`app.core.audit`, which stamps the current user id stashed on the
    session by ``get_current_user``.
    """

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), name="created_by", nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), name="updated_by", nullable=True
    )

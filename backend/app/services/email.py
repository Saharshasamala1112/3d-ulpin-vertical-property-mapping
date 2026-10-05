"""Outbound email delivery used by the password-reset flow (issue #39).

Dispatch is deliberately forgiving: when SMTP is not configured (the default
for local development and CI) the call logs a warning and returns ``False``
instead of raising, so the API contract — a generic response regardless of
whether the address exists — never depends on mail-infrastructure health.
Tests patch :func:`send_password_reset_email` to capture reset links.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("geosix.email")

_RESET_SUBJECT = "Reset your GEOSIX password"


def send_password_reset_email(recipient: str, reset_url: str) -> bool:
    """Send a password-reset link to ``recipient``. Returns True when dispatched."""
    if not settings.smtp_host:
        logger.warning("SMTP host is not configured; password-reset email was not sent")
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = _RESET_SUBJECT
    message.set_content(
        "A password reset was requested for your GEOSIX account.\n"
        "\n"
        f"Open this link to choose a new password (valid for "
        f"{settings.password_reset_expire_minutes} minutes):\n"
        "\n"
        f"    {reset_url}\n"
        "\n"
        "If you did not request this, you can safely ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except Exception:
        logger.exception("Failed to send password-reset email")
        return False

    logger.info("Password-reset email sent")
    return True

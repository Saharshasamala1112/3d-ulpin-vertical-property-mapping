from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings

#: Minimum accepted length of the JWT signing secret when ``DEBUG`` is false.
MIN_JWT_SECRET_LENGTH = 32

#: Documented, insecure-by-design secret used **only** when ``DEBUG`` is true, so
#: a developer never has to invent one to run locally. It is deliberately listed
#: in :data:`INSECURE_JWT_SECRETS`, which means copying this value from
#: ``.env.example`` into a production environment is rejected rather than
#: silently accepted.
DEBUG_ONLY_JWT_SECRET_KEY = "geosix-insecure-development-only-secret"

#: Values that are never acceptable as a production signing secret. This is a
#: short denylist of *known* values -- the placeholder that used to ship as the
#: default, the development-only secret above, and a few equally obvious
#: stand-ins. It is intentionally not a password-strength policy: entropy beyond
#: the length floor is the deployment's responsibility.
INSECURE_JWT_SECRETS = frozenset(
    {
        # Historical shipped default, removed from Settings but still seen in
        # stale .env files and CI variables.
        "change-me-in-production-use-a-real-secret",
        DEBUG_ONLY_JWT_SECRET_KEY,
        "change-me",
        "changeme",
        "change_me",
        "please-change-me",
        "placeholder",
        "replace-me",
        "replace_me",
        "your-secret-key",
        "your-secret-here",
        "your_secret_key",
        "your_secret_here",
        "secret",
        "secret-key",
        "secretkey",
        "jwt-secret",
        "jwt_secret",
        "example",
        "insecure",
        "test",
    }
)

#: Command used in error messages so the failure is actionable on its own.
SECRET_GENERATION_COMMAND = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": False,
    }

    # Application
    app_name: str = "GEOSIX API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # JWT
    # No usable default on purpose. An empty value is replaced with
    # ``DEBUG_ONLY_JWT_SECRET_KEY`` when ``DEBUG`` is true, and rejected when it
    # is false; see :meth:`_validate_jwt_secret_key`.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    # Single declaration point. This used to be declared twice in the same class
    # body, and only the second survived; a deployment reading the table in
    # docs/deployment.md must never have to guess which default is real.
    database_url: str = "postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_dev"

    # Security
    # bcrypt cost factor. Lowered only in test environments to keep the suite fast;
    # the production default must stay at the normal value.
    bcrypt_rounds: int = 12

    # Login throttling (issue #39). After ``login_max_attempts`` consecutive
    # failures for one throttle key the key is locked for
    # ``login_lockout_minutes``. State is kept in the ``login_attempts`` table.
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # Password reset
    password_reset_expire_minutes: int = 30
    #: Base URL of the frontend used to build reset links in emails.
    frontend_base_url: str = "http://localhost:5173"

    # SMTP (password reset email delivery). An empty ``smtp_host`` disables
    # dispatch: the endpoint still succeeds but logs a warning, so local
    # development and CI never require a mail server.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@geosix.local"
    smtp_starttls: bool = True

    @model_validator(mode="after")
    def _validate_jwt_secret_key(self) -> Settings:
        """Refuse to build a production configuration with a weak signing secret.

        Runs during ``Settings`` construction, so an invalid production
        configuration fails at import of :mod:`app.core.config` -- before the
        database engine in :mod:`app.core.database` and the ASGI app in
        :mod:`app.main` are ever created.

        Debug mode keeps the documented development path alive: an unset secret
        falls back to :data:`DEBUG_ONLY_JWT_SECRET_KEY`. Non-debug mode has no
        fallback and no override.
        """
        secret = self.jwt_secret_key.strip()

        if self.debug:
            if not secret:
                self.jwt_secret_key = DEBUG_ONLY_JWT_SECRET_KEY
            return self

        if not secret:
            raise ValueError(
                "JWT_SECRET_KEY is required when DEBUG is false, but it is missing or empty. "
                f"Set it explicitly to a unique value of at least {MIN_JWT_SECRET_LENGTH} "
                f"characters, for example: {SECRET_GENERATION_COMMAND}. "
                "The development-only secret is never accepted in production."
            )

        if secret.lower() in INSECURE_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY is set to a known placeholder value, which cannot be used when "
                f"DEBUG is false. Supply your own unique value of at least {MIN_JWT_SECRET_LENGTH} "
                f"characters, for example: {SECRET_GENERATION_COMMAND}."
            )

        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters long when "
                f"DEBUG is false, but the configured value is {len(secret)} characters. "
                f"Generate a longer one with: {SECRET_GENERATION_COMMAND}."
            )

        return self


settings = Settings()

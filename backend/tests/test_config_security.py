"""Production hardening of ``Settings``: the JWT signing secret (WI-31).

The signing secret is validated while ``Settings`` is being constructed, so a
non-debug configuration that cannot sign tokens safely fails before the database
engine and the ASGI app are ever created. These tests pin that behaviour in both
directions: production is held to a real secret, and the documented development
path keeps working.

Every test is isolated from ambient configuration -- ``_env_file=None`` stops
pydantic reading a developer's ``backend/.env``, and the ``isolated_env``
fixture unsets any matching variable already exported in the shell -- so results
never depend on the machine running them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEBUG_ONLY_JWT_SECRET_KEY,
    MIN_JWT_SECRET_LENGTH,
    Settings,
    settings,
)
from app.core.security import create_token, decode_token

BACKEND_DIR = Path(__file__).resolve().parents[1]

#: A syntactically valid, non-placeholder secret for the "should be accepted" cases.
VALID_SECRET = "0f8a1c93b6e24d7fa5103c8be2d94f6a17b5e0c38d724f19a6b03e5c7d81f2a4"
OTHER_VALID_SECRET = "9b3d7e15c84b2f60a7d93e1b5c48f206d7a9e35b1c8f420d6e7a3b9c15d8e2f"

#: The placeholder that used to ship as the default value of ``jwt_secret_key``.
SHIPPED_PLACEHOLDER = "change-me-in-production-use-a-real-secret"

#: A syntactically valid local URL, used only so a production import can proceed.
VALID_DATABASE_URL = "postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_test"

#: Derived from the model so the isolation cannot drift from the real field set.
_CONFIG_ENV_VARS = [name.upper() for name in Settings.model_fields]


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every ``Settings``-backed variable from the process environment."""
    for variable in _CONFIG_ENV_VARS:
        monkeypatch.delenv(variable, raising=False)


def build(**overrides) -> Settings:
    """Construct ``Settings`` from explicit inputs only, never from the environment."""
    normalized_overrides = {name.lower(): value for name, value in overrides.items()}
    return Settings(_env_file=None, **normalized_overrides)


class TestNoSecretShipsAsADefault:
    """The field itself must not carry a usable secret any more."""

    def test_jwt_secret_key_has_no_real_placeholder_default(self) -> None:
        assert Settings.model_fields["jwt_secret_key"].default == ""

    def test_shipped_placeholder_is_not_a_valid_default_anywhere(self) -> None:
        assert SHIPPED_PLACEHOLDER not in Settings.model_fields["jwt_secret_key"].default


class TestProductionSecretValidation:
    """``DEBUG=false`` must never build with a missing, placeholder or short secret."""

    def test_missing_secret_is_rejected(self, isolated_env: None) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false")

        assert "JWT_SECRET_KEY" in str(excinfo.value)

    def test_empty_secret_is_rejected(self, isolated_env: None) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY="")

        assert "JWT_SECRET_KEY" in str(excinfo.value)

    @pytest.mark.parametrize("blank", [" ", "\t", "   \n  "])
    def test_whitespace_only_secret_is_rejected(self, isolated_env: None, blank: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY=blank)

        assert "JWT_SECRET_KEY" in str(excinfo.value)

    def test_shipped_placeholder_is_rejected(self, isolated_env: None) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY=SHIPPED_PLACEHOLDER)

        assert "placeholder" in str(excinfo.value).lower()

    def test_documented_development_secret_is_rejected(self, isolated_env: None) -> None:
        """Copying the .env.example development value into production must fail."""
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY=DEBUG_ONLY_JWT_SECRET_KEY)

        assert "JWT_SECRET_KEY" in str(excinfo.value)

    @pytest.mark.parametrize(
        "placeholder",
        ["changeme", "change-me", "please-change-me", "your-secret-key", "secret", "placeholder"],
    )
    def test_other_known_placeholders_are_rejected(
        self, isolated_env: None, placeholder: str
    ) -> None:
        with pytest.raises(ValidationError):
            build(DEBUG="false", JWT_SECRET_KEY=placeholder)

    @pytest.mark.parametrize("length", [1, 8, 16, 31])
    def test_secret_shorter_than_minimum_is_rejected(self, isolated_env: None, length: int) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY="a" * length)

        assert "32" in str(excinfo.value)

    def test_placeholder_is_rejected_regardless_of_case(self, isolated_env: None) -> None:
        with pytest.raises(ValidationError):
            build(DEBUG="false", JWT_SECRET_KEY=SHIPPED_PLACEHOLDER.upper())

    def test_secret_of_exactly_minimum_length_is_accepted(self, isolated_env: None) -> None:
        secret = "a" * MIN_JWT_SECRET_LENGTH

        configured = build(DEBUG="false", JWT_SECRET_KEY=secret)

        assert configured.jwt_secret_key == secret
        assert configured.debug is False

    def test_long_secret_is_accepted(self, isolated_env: None) -> None:
        configured = build(DEBUG="false", JWT_SECRET_KEY=VALID_SECRET)

        assert configured.jwt_secret_key == VALID_SECRET

    def test_production_settings_expose_database_url(self, isolated_env: None) -> None:
        """A valid production configuration still builds the values Alembic needs."""
        configured = build(DEBUG="false", JWT_SECRET_KEY=VALID_SECRET)

        assert configured.database_url
        assert configured.jwt_algorithm == "HS256"

    def test_existing_production_settings_fixture_still_builds(
        self, production_settings: Settings
    ) -> None:
        """The pre-existing fixture must keep working; it uses the default DEBUG."""
        assert production_settings.bcrypt_rounds == 12
        assert production_settings.jwt_secret_key


class TestDevelopmentSecretPath:
    """The documented development path stays convenient and is not a hidden default."""

    def test_debug_mode_without_secret_uses_documented_development_secret(
        self, isolated_env: None
    ) -> None:
        configured = build(DEBUG="true")

        assert configured.jwt_secret_key == DEBUG_ONLY_JWT_SECRET_KEY
        assert configured.debug is True

    def test_debug_mode_accepts_the_explicit_development_secret(self, isolated_env: None) -> None:
        """This is the value documented in .env.example for local development."""
        configured = build(DEBUG="true", JWT_SECRET_KEY=DEBUG_ONLY_JWT_SECRET_KEY)

        assert configured.jwt_secret_key == DEBUG_ONLY_JWT_SECRET_KEY

    def test_debug_mode_keeps_a_supplied_secret(self, isolated_env: None) -> None:
        """A developer-supplied secret is never overwritten."""
        configured = build(DEBUG="true", JWT_SECRET_KEY=VALID_SECRET)

        assert configured.jwt_secret_key == VALID_SECRET

    def test_debug_mode_does_not_require_a_long_secret(self, isolated_env: None) -> None:
        """Development is deliberately unconstrained; production is not."""
        configured = build(DEBUG="true", JWT_SECRET_KEY="dev")

        assert configured.jwt_secret_key == "dev"

    def test_development_secret_is_long_enough_to_be_caught_by_the_denylist(self) -> None:
        """It clears the 32-character floor, so only the denylist can stop it."""
        assert len(DEBUG_ONLY_JWT_SECRET_KEY) >= MIN_JWT_SECRET_LENGTH

    def test_module_level_settings_uses_the_development_path(self, isolated_env: None) -> None:
        """The process-wide instance is importable, so local development is not blocked."""
        assert settings.debug is True
        assert settings.jwt_secret_key == DEBUG_ONLY_JWT_SECRET_KEY


class TestErrorMessagesAreActionable:
    """A failure must name the variable and state the minimum length."""

    @pytest.mark.parametrize(
        ("overrides", "expected_fragment"),
        [
            ({"DEBUG": "false"}, "missing or empty"),
            ({"DEBUG": "false", "JWT_SECRET_KEY": ""}, "missing or empty"),
            ({"DEBUG": "false", "JWT_SECRET_KEY": SHIPPED_PLACEHOLDER}, "placeholder"),
            ({"DEBUG": "false", "JWT_SECRET_KEY": DEBUG_ONLY_JWT_SECRET_KEY}, "placeholder"),
            ({"DEBUG": "false", "JWT_SECRET_KEY": "a" * 31}, "31 characters"),
        ],
    )
    def test_message_names_the_variable_and_the_minimum(
        self, isolated_env: None, overrides: dict, expected_fragment: str
    ) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(**overrides)

        message = str(excinfo.value)
        assert "JWT_SECRET_KEY" in message
        assert str(MIN_JWT_SECRET_LENGTH) in message
        assert expected_fragment in message

    def test_short_secret_message_suggests_how_to_generate_one(self, isolated_env: None) -> None:
        with pytest.raises(ValidationError) as excinfo:
            build(DEBUG="false", JWT_SECRET_KEY="too-short")

        assert "secrets.token_urlsafe" in str(excinfo.value)


class TestFailurePrecedesApplicationStartup:
    """Construction fails before the engine or the ASGI app exist."""

    def test_production_config_failure_precedes_database_and_app(self, tmp_path: Path) -> None:
        script = (
            "import sys\n"
            "try:\n"
            "    import app.main\n"
            "except Exception as exc:\n"
            "    print('FAILED', type(exc).__name__)\n"
            "else:\n"
            "    print('IMPORTED')\n"
            "print('database_loaded', 'app.core.database' in sys.modules)\n"
            "print('main_loaded', 'app.main' in sys.modules)\n"
        )
        env = {key: value for key, value in os.environ.items() if key not in _CONFIG_ENV_VARS}
        env["PYTHONPATH"] = str(BACKEND_DIR)
        env["DEBUG"] = "false"
        # cwd is an empty directory so no stray .env can satisfy the secret.
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert "FAILED ValidationError" in result.stdout
        assert "database_loaded False" in result.stdout
        assert "main_loaded False" in result.stdout

    def test_valid_production_config_imports_cleanly(self, tmp_path: Path) -> None:
        script = "import app.main\nprint('OK', app.main.settings.debug)\n"
        env = {key: value for key, value in os.environ.items() if key not in _CONFIG_ENV_VARS}
        env["PYTHONPATH"] = str(BACKEND_DIR)
        env["DEBUG"] = "false"
        env["JWT_SECRET_KEY"] = VALID_SECRET
        env["DATABASE_URL"] = VALID_DATABASE_URL
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert "OK False" in result.stdout


class TestJwtStillWorks:
    """Signing and verification behaviour is unchanged for a valid secret."""

    def test_access_token_round_trips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", VALID_SECRET)

        token = create_token("user-123", "access")
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_refresh_token_round_trips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", VALID_SECRET)

        payload = decode_token(create_token("user-123", "refresh"))

        assert payload is not None
        assert payload["type"] == "refresh"

    def test_token_signed_with_another_secret_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", VALID_SECRET)
        token = create_token("user-123", "access")

        monkeypatch.setattr(settings, "jwt_secret_key", OTHER_VALID_SECRET)

        assert decode_token(token) is None

    def test_tampered_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", VALID_SECRET)
        token = create_token("user-123", "access")

        assert decode_token(token + "x") is None

    def test_garbage_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", VALID_SECRET)

        assert decode_token("not-a-token") is None

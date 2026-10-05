from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings
from app.core.dependencies import CurrentUser, DatabaseSession
from app.main import app
from app.models.audit import AuditColumns
from app.models.login_attempt import LoginAttempt
from app.models.password_reset_token import PasswordResetToken
from app.services.login_throttle import email_key, ip_key
from tests.auth_support import EDITOR_ID, SEED_EMAILS, bearer_headers

DATA_PREFIXES = (
    "/api/v1/parcels",
    "/api/v1/buildings",
    "/api/v1/floors",
    "/api/v1/units",
    "/api/v1/vdc",
    "/api/v1/topology",
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
DATA_OPERATIONS = [
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    if path.startswith(DATA_PREFIXES)
    for method in operations
    if method in HTTP_METHODS
]
WRITE_OPERATIONS = [
    (method, path) for method, path in DATA_OPERATIONS if method in {"POST", "PUT", "PATCH"}
]
READ_OPERATIONS = [(method, path) for method, path in DATA_OPERATIONS if method == "GET"]
DELETE_OPERATIONS = [(method, path) for method, path in DATA_OPERATIONS if method == "DELETE"]


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda _match: str(uuid4()), path)


def _call(client: TestClient, method: str, path: str):
    kwargs = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
    return client.request(method, _concrete_path(path), **kwargs)


def _client(role: str | None = None) -> TestClient:
    headers = bearer_headers(role) if role else None
    return TestClient(app, headers=headers, raise_server_exceptions=False)


@pytest.mark.parametrize(("method", "path"), DATA_OPERATIONS)
def test_every_data_endpoint_requires_authentication(method: str, path: str) -> None:
    response = _call(_client(), method, path)

    assert response.status_code == 401, f"{method} {path} was not rejected with 401"


@pytest.mark.parametrize(("method", "path"), READ_OPERATIONS)
def test_readers_are_admitted_to_read_endpoints(method: str, path: str) -> None:
    response = _call(_client("reader"), method, path)

    assert response.status_code not in {401, 403}, f"reader was denied {method} {path}"


@pytest.mark.parametrize(("method", "path"), WRITE_OPERATIONS)
def test_readers_cannot_write_any_data_endpoint(method: str, path: str) -> None:
    response = _call(_client("reader"), method, path)

    assert response.status_code == 403, f"reader reached {method} {path}"


@pytest.mark.parametrize(("method", "path"), WRITE_OPERATIONS)
def test_editors_are_admitted_to_write_endpoints(method: str, path: str) -> None:
    response = _call(_client("editor"), method, path)

    assert response.status_code != 403, f"editor was denied {method} {path}"


@pytest.mark.parametrize(("method", "path"), DELETE_OPERATIONS)
def test_only_admins_are_admitted_to_destructive_endpoints(method: str, path: str) -> None:
    reader_response = _call(_client("reader"), method, path)
    editor_response = _call(_client("editor"), method, path)
    admin_response = _call(_client("admin"), method, path)

    assert reader_response.status_code == 403
    assert editor_response.status_code == 403
    assert admin_response.status_code != 403


@pytest.mark.parametrize("role", ["reader", "editor"])
def test_only_admins_can_list_or_assign_roles(role: str) -> None:
    client = _client(role)

    assert client.get("/api/v1/auth/users").status_code == 403
    response = client.patch(
        f"/api/v1/auth/users/{uuid4()}/role",
        json={"role": "editor"},
    )
    assert response.status_code == 403


def test_admin_can_list_users_and_assign_a_role() -> None:
    client = _client("admin")

    users = client.get("/api/v1/auth/users")
    assert users.status_code == 200
    assert {user["role"] for user in users.json()} == {"reader", "editor", "admin"}

    response = client.patch(
        "/api/v1/auth/users/00000000-0000-0000-0000-0000000000f1/role",
        json={"role": "editor"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


def test_failed_login_locks_email_and_ip_then_recovers(
    sqlite_auth_database: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "login_max_attempts", 2)
    client = _client()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "incorrect"},
    )
    assert response.status_code == 401
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "incorrect"},
    )
    assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "geosix-rbac-test-password"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]

    now = datetime.now(timezone.utc)
    with sqlite_auth_database() as db:
        rows = db.scalars(select(LoginAttempt)).all()
        assert {row.subject for row in rows} == {
            email_key(SEED_EMAILS["reader"]),
            ip_key("testclient"),
        }
        for row in rows:
            row.locked_until = now - timedelta(seconds=1)
        db.commit()

    recovered = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "geosix-rbac-test-password"},
    )
    assert recovered.status_code == 200
    with sqlite_auth_database() as db:
        assert db.scalars(select(LoginAttempt)).all() == []


def test_password_reset_is_emailed_hashed_expiring_and_single_use(
    sqlite_auth_database: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[tuple[str, str]] = []

    def send_email(recipient: str, reset_url: str) -> bool:
        dispatched.append((recipient, reset_url))
        return True

    monkeypatch.setattr("app.services.password_reset.send_password_reset_email", send_email)
    client = _client()
    requested = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": SEED_EMAILS["reader"]},
    )
    assert requested.status_code == 200
    assert requested.json()["message"] == "If the email exists, a reset link has been sent"
    assert dispatched[0][0] == SEED_EMAILS["reader"]

    token = parse_qs(urlparse(dispatched[0][1]).query)["token"][0]
    with sqlite_auth_database() as db:
        row = db.scalar(select(PasswordResetToken))
        assert row is not None
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert row.token_hash != token

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "new-password-123"},
    )
    assert reset.status_code == 200
    reused = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "another-password-123"},
    )
    assert reused.status_code == 400

    old_password = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "geosix-rbac-test-password"},
    )
    new_password = client.post(
        "/api/v1/auth/login",
        json={"email": SEED_EMAILS["reader"], "password": "new-password-123"},
    )
    assert old_password.status_code == 401
    assert new_password.status_code == 200


def test_expired_password_reset_token_is_rejected(
    sqlite_auth_database: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.services.password_reset.send_password_reset_email",
        lambda _recipient, url: dispatched.append(url) or True,
    )
    client = _client()
    client.post(
        "/api/v1/auth/forgot-password",
        json={"email": SEED_EMAILS["reader"]},
    )
    token = parse_qs(urlparse(dispatched[0]).query)["token"][0]

    with sqlite_auth_database() as db:
        row = db.scalar(select(PasswordResetToken))
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "new-password-123"},
    )
    assert response.status_code == 400


def test_unknown_reset_email_has_the_same_response_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.services.password_reset.send_password_reset_email",
        lambda _recipient, url: dispatched.append(url) or True,
    )
    response = _client().post(
        "/api/v1/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "If the email exists, a reset link has been sent"
    assert dispatched == []


class _AuditBase(DeclarativeBase):
    pass


class _AuditRecord(AuditColumns, _AuditBase):
    __tablename__ = "auth_audit_test_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(40), nullable=False)


def _create_audit_record(db: DatabaseSession, _user: CurrentUser) -> dict[str, str | int]:
    record = _AuditRecord(value="created")
    db.add(record)
    db.commit()
    return {
        "id": record.id,
        "created_by": str(record.created_by),
        "updated_by": str(record.updated_by),
    }


def _update_audit_record(
    record_id: int,
    db: DatabaseSession,
    _user: CurrentUser,
) -> dict[str, str | int]:
    record = db.get(_AuditRecord, record_id)
    assert record is not None
    record.value = "updated"
    db.commit()
    return {
        "id": record.id,
        "created_by": str(record.created_by),
        "updated_by": str(record.updated_by),
    }


app.add_api_route(
    "/__test__/audit-records",
    _create_audit_record,
    methods=["POST"],
    include_in_schema=False,
)
app.add_api_route(
    "/__test__/audit-records/{record_id}",
    _update_audit_record,
    methods=["PUT"],
    include_in_schema=False,
)


def test_audit_listener_stamps_api_actor_on_create_and_update(
    sqlite_auth_database: sessionmaker,
) -> None:
    engine = sqlite_auth_database.kw["bind"]
    _AuditBase.metadata.create_all(engine)
    client = _client("editor")

    created = client.post("/__test__/audit-records")
    assert created.status_code == 200
    assert created.json()["created_by"] == str(EDITOR_ID)
    assert created.json()["updated_by"] == str(EDITOR_ID)

    updated = client.put(f"/__test__/audit-records/{created.json()['id']}")
    assert updated.status_code == 200
    assert updated.json()["created_by"] == str(EDITOR_ID)
    assert updated.json()["updated_by"] == str(EDITOR_ID)

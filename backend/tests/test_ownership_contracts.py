from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.dependencies import get_current_user
from app.main import create_app
from app.schemas.ownership import OwnershipGrant, OwnerUpdate


def test_owner_patch_requires_a_non_null_mutable_field() -> None:
    with pytest.raises(ValidationError):
        OwnerUpdate()
    with pytest.raises(ValidationError):
        OwnerUpdate(name=None)
    with pytest.raises(ValidationError):
        OwnerUpdate(kind=None)


def test_grant_requires_timezone_aware_effective_date() -> None:
    with pytest.raises(ValidationError):
        OwnershipGrant(
            subject_type="parcel",
            subject_id="00000000-0000-0000-0000-000000000001",
            owner_id="00000000-0000-0000-0000-000000000002",
            share_basis_points=5000,
            valid_from=datetime(2026, 9, 30),
        )


def test_write_endpoint_fails_closed_until_feature_2_authorization_exists() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-user",
        "is_active": True,
    }
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post(
            "/api/v1/ownership/owners",
            json={"kind": "individual", "name": "Test Owner"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 501
    assert response.json() == {
        "error_code": "OWNERSHIP_AUTHORIZATION_UNAVAILABLE",
        "message": "Ownership writes require the Feature 2 authorization policy",
        "details": {},
    }

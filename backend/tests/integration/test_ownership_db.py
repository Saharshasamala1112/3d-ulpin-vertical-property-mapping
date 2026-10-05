from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.ownership import Owner, OwnershipInterest
from app.models.parcel import Parcel
from tests.integration import factories

pytestmark = pytest.mark.integration


def _owner(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/v1/ownership/owners",
        json={"kind": "individual", "name": name, "contact_metadata": {"source": "test"}},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _grant(
    client: TestClient,
    owner_id: str,
    subject_type: str,
    subject_id: str,
    share: int,
    valid_from: datetime,
):
    return client.post(
        "/api/v1/ownership/interests",
        json={
            "owner_id": owner_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "share_basis_points": share,
            "valid_from": valid_from.isoformat(),
        },
    )


def _assert_error(response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"error_code", "message", "details"}
    assert body["error_code"] == code
    assert isinstance(body["details"], dict)
    return body


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_owner_crud_and_delete_with_history_rejected(
    ownership_client: TestClient, parcel, db_session: Session
) -> None:
    client = ownership_client
    owner = _owner(client, "Owner CRUD")
    owner_id = owner["id"]

    assert client.get(f"/api/v1/ownership/owners/{owner_id}").json()["name"] == "Owner CRUD"
    updated = client.patch(f"/api/v1/ownership/owners/{owner_id}", json={"name": "Updated Owner"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Owner"
    assert client.delete(f"/api/v1/ownership/owners/{owner_id}").status_code == 204

    referenced = _owner(client, "Owner With History")
    grant = _grant(
        client,
        referenced["id"],
        "parcel",
        str(parcel.id),
        10000,
        datetime.now(timezone.utc) - timedelta(days=2),
    )
    assert grant.status_code == 201, grant.text
    _assert_error(
        client.delete(f"/api/v1/ownership/owners/{referenced['id']}"),
        409,
        "OWNERSHIP_HISTORY_IMMUTABLE",
    )


def test_grant_parcel_and_unit_and_list_by_subject_and_owner(
    ownership_client: TestClient, parcel, unit
) -> None:
    client = ownership_client
    owner = _owner(client, "Parcel and Unit Owner")
    start = datetime.now(timezone.utc) - timedelta(days=1)
    parcel_grant = _grant(client, owner["id"], "parcel", str(parcel.id), 3500, start)
    unit_grant = _grant(client, owner["id"], "unit", str(unit.id), 10000, start)
    assert parcel_grant.status_code == unit_grant.status_code == 201

    parcel_rows = client.get(f"/api/v1/ownership/parcels/{parcel.id}/interests").json()["data"]
    unit_rows = client.get(f"/api/v1/ownership/units/{unit.id}/interests").json()["data"]
    owner_rows = client.get(
        f"/api/v1/ownership/owners/{owner['id']}/interests", params={"history": True}
    ).json()["data"]
    assert [(row["subject_type"], row["share_basis_points"]) for row in parcel_rows] == [
        ("parcel", 3500)
    ]
    assert [(row["subject_type"], row["share_basis_points"]) for row in unit_rows] == [
        ("unit", 10000)
    ]
    assert len(owner_rows) == 2


def test_share_limit_overlap_and_invalid_subject_errors(
    ownership_client: TestClient, parcel
) -> None:
    client = ownership_client
    first = _owner(client, "First Share Owner")
    second = _owner(client, "Second Share Owner")
    start = datetime.now(timezone.utc) - timedelta(days=2)
    invalid_share = _grant(client, first["id"], "parcel", str(parcel.id), 10001, start)
    body = _assert_error(invalid_share, 422, "VALIDATION_ERROR")
    assert "share_basis_points" in body["details"]
    assert _grant(client, first["id"], "parcel", str(parcel.id), 7000, start).status_code == 201

    over_limit = _grant(client, second["id"], "parcel", str(parcel.id), 3001, start)
    _assert_error(over_limit, 409, "OWNERSHIP_SHARE_LIMIT_EXCEEDED")
    assert (
        ownership_client.get(
            f"/api/v1/ownership/owners/{second['id']}/interests", params={"history": True}
        ).json()["meta"]["total"]
        == 0
    )

    overlapping = _grant(
        client, first["id"], "parcel", str(parcel.id), 1000, start + timedelta(days=1)
    )
    _assert_error(overlapping, 409, "OWNERSHIP_INTERVAL_OVERLAP")

    missing = _grant(client, second["id"], "parcel", str(uuid.uuid4()), 100, start)
    _assert_error(missing, 404, "NOT_FOUND")

    invalid_date = client.post(
        "/api/v1/ownership/interests",
        json={
            "owner_id": second["id"],
            "subject_type": "parcel",
            "subject_id": str(parcel.id),
            "share_basis_points": 100,
            "valid_from": "2026-09-30T00:00:00",
        },
    )
    body = _assert_error(invalid_date, 422, "VALIDATION_ERROR")
    assert "valid_from" in body["details"]


def test_interest_listing_reports_missing_resources_and_invalid_effective_date(
    ownership_client: TestClient,
) -> None:
    client = ownership_client
    missing_parcel = client.get(f"/api/v1/ownership/parcels/{uuid.uuid4()}/interests")
    _assert_error(missing_parcel, 404, "NOT_FOUND")

    missing_owner = client.get(f"/api/v1/ownership/owners/{uuid.uuid4()}/interests")
    _assert_error(missing_owner, 404, "NOT_FOUND")

    owner = _owner(client, "Date Filter Owner")
    response = client.get(
        f"/api/v1/ownership/owners/{owner['id']}/interests",
        params={"effective_at": "2026-09-30T12:00:00"},
    )
    body = _assert_error(response, 422, "VALIDATION_ERROR")
    assert "effective_at" in body["details"]


def test_non_overlapping_regrant_and_revocation_preserve_history(
    ownership_client: TestClient, parcel
) -> None:
    client = ownership_client
    owner = _owner(client, "Regrant Owner")
    start = datetime.now(timezone.utc) - timedelta(days=5)
    original = _grant(client, owner["id"], "parcel", str(parcel.id), 5000, start).json()
    revoked_at = start + timedelta(days=2)
    revoked = client.post(
        f"/api/v1/ownership/interests/{original['id']}/revocations",
        json={"effective_at": revoked_at.isoformat()},
    )
    assert revoked.status_code == 200
    assert _as_datetime(revoked.json()["valid_to"]) == revoked_at
    assert revoked.json()["status"] == "revoked"

    later = _grant(
        client,
        owner["id"],
        "parcel",
        str(parcel.id),
        2500,
        revoked_at + timedelta(seconds=1),
    )
    assert later.status_code == 201, later.text
    again = client.post(
        f"/api/v1/ownership/interests/{original['id']}/revocations",
        json={"effective_at": (revoked_at + timedelta(days=1)).isoformat()},
    )
    _assert_error(again, 409, "OWNERSHIP_HISTORY_IMMUTABLE")

    history = client.get(
        f"/api/v1/ownership/owners/{owner['id']}/interests", params={"history": True}
    ).json()["data"]
    assert len(history) == 2
    assert client.delete(f"/api/v1/ownership/interests/{original['id']}").status_code == 404


def test_transfer_is_complete_atomic_and_preserves_allocation_history(
    ownership_client: TestClient, parcel
) -> None:
    client = ownership_client
    alice = _owner(client, "Alice")
    bob = _owner(client, "Bob")
    charlie = _owner(client, "Charlie")
    start = datetime.now(timezone.utc) - timedelta(days=3)
    first = _grant(client, alice["id"], "parcel", str(parcel.id), 6000, start).json()
    second = _grant(client, bob["id"], "parcel", str(parcel.id), 4000, start).json()
    effective_at = datetime.now(timezone.utc) + timedelta(seconds=2)

    response = client.post(
        "/api/v1/ownership/transfers",
        json={
            "subject_type": "parcel",
            "subject_id": str(parcel.id),
            "effective_at": effective_at.isoformat(),
            "allocations": [
                {"owner_id": alice["id"], "share_basis_points": 4000},
                {"owner_id": bob["id"], "share_basis_points": 4000},
                {"owner_id": charlie["id"], "share_basis_points": 2000},
            ],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert {row["id"] for row in result["closed"]} == {first["id"], second["id"]}
    assert all(_as_datetime(row["valid_to"]) == effective_at for row in result["closed"])
    assert sum(row["share_basis_points"] for row in result["created"]) == 10000

    failed_time = effective_at + timedelta(days=1)
    failed = client.post(
        "/api/v1/ownership/transfers",
        json={
            "subject_type": "parcel",
            "subject_id": str(parcel.id),
            "effective_at": failed_time.isoformat(),
            "allocations": [{"owner_id": alice["id"], "share_basis_points": 9999}],
        },
    )
    _assert_error(failed, 409, "OWNERSHIP_TRANSFER_INVALID")
    history = client.get(
        f"/api/v1/ownership/parcels/{parcel.id}/interests", params={"history": True}
    ).json()["data"]
    assert len(history) == 5
    assert all(row["valid_to"] is None for row in history if row["status"] == "active")

    before = client.get(
        f"/api/v1/ownership/parcels/{parcel.id}/interests",
        params={"effective_at": (effective_at - timedelta(seconds=1)).isoformat()},
    ).json()["data"]
    after = client.get(
        f"/api/v1/ownership/parcels/{parcel.id}/interests",
        params={"effective_at": (effective_at + timedelta(seconds=1)).isoformat()},
    ).json()["data"]
    assert len(before) == 2
    assert len(after) == 3


def test_concurrent_grants_serialize_on_subject_row(engine: Engine) -> None:
    """Two independent PostgreSQL sessions cannot over-allocate a parcel."""
    independent_factory = sessionmaker(bind=engine, expire_on_commit=False)
    setup = independent_factory()
    try:
        parcel = factories.parcel_factory(setup)
        first_owner = factories.owner_factory(setup, name="Concurrent A")
        second_owner = factories.owner_factory(setup, name="Concurrent B")
        parcel_id = parcel.id
        first_id = first_owner.id
        second_id = second_owner.id
        setup.commit()
    finally:
        setup.close()

    effective_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    def attempt(owner_id: uuid.UUID) -> str:
        session = independent_factory()
        try:
            data = __import__("app.schemas.ownership", fromlist=["OwnershipGrant"]).OwnershipGrant(
                owner_id=owner_id,
                subject_type="parcel",
                subject_id=parcel_id,
                share_basis_points=6000,
                valid_from=effective_at,
            )
            from app.services.ownership import OwnershipError, grant_interest

            try:
                grant_interest(session, data)
                return "created"
            except OwnershipError as error:
                return error.code
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(attempt, [first_id, second_id]))
        assert outcomes.count("created") == 1
        assert outcomes.count("OWNERSHIP_SHARE_LIMIT_EXCEEDED") == 1
    finally:
        cleanup = independent_factory()
        try:
            cleanup.query(OwnershipInterest).filter(
                OwnershipInterest.parcel_id == parcel_id
            ).delete(synchronize_session=False)
            cleanup.query(Owner).filter(Owner.id.in_([first_id, second_id])).delete(
                synchronize_session=False
            )
            cleanup.query(Parcel).filter(Parcel.id == parcel_id).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()

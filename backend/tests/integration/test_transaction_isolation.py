"""Proof that the session fixture isolates tests despite service-level ``commit()``.

Every application service calls ``db.commit()``. If the fixture handed a test a
plain session, those commits would reach PostgreSQL and leak between tests.
The fixture instead binds the session to an outer transaction with
``join_transaction_mode="conditional_savepoint"``, so a service commit only
releases a SAVEPOINT.

These tests pin that behaviour down two ways:

* an **independent connection** cannot see rows the API "committed", proving no
  real COMMIT is issued; and
* a **later test** cannot see rows an **earlier** test committed, proving the
  fixture's teardown rollback actually discards them.

Tests within a module run in definition order, which the second test relies on.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.floor import Floor, FloorType
from app.models.parcel import Parcel
from app.models.unit import Unit, UnitStatus, UnitType
from tests.integration import factories

pytestmark = pytest.mark.integration

PARCEL_PAYLOAD = {
    "parcel_identifier": "PARCEL-ISOLATION",
    "ulpin": "ULPIN-ISOLATION",
    "geometry": {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [77.50, 12.90],
                    [77.60, 12.90],
                    [77.60, 13.00],
                    [77.50, 13.00],
                    [77.50, 12.90],
                ]
            ]
        ],
    },
    "area_sqm": 1500.0,
    "status": "active",
    "metadata": {"isolation": "test"},
}


@pytest.fixture(scope="module")
def committed_row_ids() -> list[str]:
    """Collects ids committed by the first test, for the leak check in the second."""
    return []


def _independent_session(engine: Engine) -> Session:
    """A session on its own connection, outside the test's transaction."""
    return sessionmaker(bind=engine)()


def test_a_service_commit_is_not_visible_to_other_connections(
    client: TestClient,
    db_session: Session,
    engine: Engine,
    committed_row_ids: list[str],
) -> None:
    """A row the API created and committed stays inside the outer transaction.

    The service calls ``db.commit()`` and the row is readable through the test's
    own session, yet a completely separate connection cannot see it. That is
    only possible if the "commit" released a SAVEPOINT nested inside an
    uncommitted outer transaction.
    """
    response = client.post("/api/v1/parcels", json=PARCEL_PAYLOAD)
    assert response.status_code == 201, response.text
    parcel_id = response.json()["id"]
    committed_row_ids.append(parcel_id)

    # Visible to the test's own session ...
    assert db_session.get(Parcel, parcel_id) is not None
    assert client.get(f"/api/v1/parcels/{parcel_id}").status_code == 200

    # ... but invisible to any other connection, i.e. nothing was really committed.
    independent = _independent_session(engine)
    try:
        assert independent.get(Parcel, parcel_id) is None
    finally:
        independent.close()


def test_b_rows_from_the_previous_test_were_rolled_back(
    engine: Engine, committed_row_ids: list[str]
) -> None:
    """After the previous test's teardown, its committed rows are gone.

    This is the property that makes the suite order-independent and repeatable.
    """
    assert committed_row_ids, "expected the preceding test to have committed a row"
    independent = _independent_session(engine)
    try:
        for row_id in committed_row_ids:
            assert independent.get(Parcel, row_id) is None, (
                f"row {row_id} survived the fixture rollback and leaked"
            )
        # Nothing from any test in this package is left behind.
        assert (
            independent.execute(
                select(Parcel.id).where(
                    Parcel.parcel_identifier == PARCEL_PAYLOAD["parcel_identifier"]
                )
            )
            .scalars()
            .all()
            == []
        )
    finally:
        independent.close()
    committed_row_ids.clear()


def test_factory_writes_are_visible_in_session_but_not_committed(
    db_session: Session, engine: Engine
) -> None:
    """Factory rows are readable in-session and uncommitted on the server."""
    parcel = factories.parcel_factory(db_session, parcel_identifier="PARCEL-UNCOMMITTED")

    assert db_session.get(Parcel, parcel.id) is not None

    independent = _independent_session(engine)
    try:
        assert independent.get(Parcel, parcel.id) is None
    finally:
        independent.close()


def test_repeated_commits_stay_in_one_transaction(db_session: Session, engine: Engine) -> None:
    """Four sequential service-style commits behave as one uncommitted unit.

    Also exercises the enum fix: values must survive each commit boundary as the
    lowercase labels PostgreSQL actually stores.
    """
    parcel = factories.parcel_factory(db_session, parcel_identifier="PARCEL-CHAIN")
    db_session.commit()
    building = factories.building_factory(db_session, parcel=parcel)
    db_session.commit()
    floor = factories.floor_factory(db_session, building=building)
    db_session.commit()
    unit = factories.unit_factory(db_session, floor=floor)
    db_session.commit()

    assert db_session.get(Parcel, parcel.id) is not None
    assert db_session.get(Building, building.id) is not None
    assert db_session.get(Floor, floor.id) is not None
    assert db_session.get(Unit, unit.id) is not None

    assert parcel.status.value == "active"
    assert building.building_type is BuildingType.RESIDENTIAL
    assert building.construction_status is ConstructionStatus.COMPLETED
    assert floor.floor_type is FloorType.GROUND
    assert unit.unit_type is UnitType.RESIDENTIAL
    assert unit.status is UnitStatus.ACTIVE
    assert unit.area_sqm == Decimal("75.0")

    # Even after four commits, nothing reached the server.
    independent = _independent_session(engine)
    try:
        assert independent.get(Unit, unit.id) is None
    finally:
        independent.close()


def test_failed_request_leaves_no_partial_state(
    client: TestClient, db_session: Session, engine: Engine
) -> None:
    """A rejected request persists nothing and leaves earlier work untouched.

    Note this test deliberately does *not* call ``db_session.rollback()``: the
    ``db_session`` fixture owns transaction cleanup, and an inner rollback
    deassociates the outer transaction (see the fixture's teardown guard).
    """
    first = factories.parcel_factory(db_session, parcel_identifier="PARCEL-KEEP")
    db_session.commit()
    first_id = first.id

    # A duplicate ulpin is rejected with 409 and must not create a second row.
    duplicate = client.post(
        "/api/v1/parcels",
        json={
            "parcel_identifier": "PARCEL-DUPLICATE-ATTEMPT",
            "ulpin": first.ulpin,
            "geometry": PARCEL_PAYLOAD["geometry"],
            "area_sqm": 10.0,
            "status": "draft",
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    # The original row is untouched and the rejected one was never created.
    assert client.get(f"/api/v1/parcels/{first_id}").status_code == 200
    rejected_count = (
        db_session.query(Parcel)
        .filter(Parcel.parcel_identifier == "PARCEL-DUPLICATE-ATTEMPT")
        .count()
    )
    assert rejected_count == 0

    # Work after the failure still works and remains isolated.
    replacement = factories.parcel_factory(db_session, parcel_identifier="PARCEL-REPLACEMENT")
    db_session.commit()
    assert client.get(f"/api/v1/parcels/{replacement.id}").status_code == 200

    independent = _independent_session(engine)
    try:
        assert independent.get(Parcel, replacement.id) is None
    finally:
        independent.close()

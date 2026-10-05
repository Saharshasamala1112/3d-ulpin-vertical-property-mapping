from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.geometry3d import PropertyGeometry
from app.models.unit import Unit
from tests.integration.factories import property_geometry_factory

pytestmark = pytest.mark.integration


def _assert_rejected(db_session, unit: Unit, **overrides) -> str:
    """Assert that ``overrides`` is refused by a ``property_geometry`` constraint.

    The insert runs inside a nested SAVEPOINT. A bare failed flush makes
    SQLAlchemy roll back the connection's whole transaction, which deassociates
    the ``db_session`` fixture's outer transaction and then trips its teardown
    guard. Rolling back to the SAVEPOINT instead leaves that outer transaction
    intact, so the suite's isolation guarantee still holds and the session
    remains usable afterwards.
    """
    with pytest.raises(IntegrityError) as exc_info:
        with db_session.begin_nested():
            property_geometry_factory(db_session, unit, **overrides)
    return str(exc_info.value).lower()


def test_valid_bounding_box_accepted(db_session, unit: Unit):
    """A valid bounding box (x_min < x_max, y_min < y_max, z_min < z_max) is accepted."""
    geometry = property_geometry_factory(db_session, unit)

    db_session.commit()

    assert geometry.id is not None
    assert geometry.unit_id == unit.id


def test_x_min_equals_x_max_rejected(db_session, unit: Unit):
    """x_min == x_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, x_min=Decimal("5"), x_max=Decimal("5"))

    assert "ck_property_geometry_x_min_lt_x_max" in message


def test_x_min_greater_than_x_max_rejected(db_session, unit: Unit):
    """x_min > x_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, x_min=Decimal("10"), x_max=Decimal("5"))

    assert "ck_property_geometry_x_min_lt_x_max" in message


def test_y_min_equals_y_max_rejected(db_session, unit: Unit):
    """y_min == y_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, y_min=Decimal("5"), y_max=Decimal("5"))

    assert "ck_property_geometry_y_min_lt_y_max" in message


def test_y_min_greater_than_y_max_rejected(db_session, unit: Unit):
    """y_min > y_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, y_min=Decimal("10"), y_max=Decimal("5"))

    assert "ck_property_geometry_y_min_lt_y_max" in message


def test_z_min_equals_z_max_rejected(db_session, unit: Unit):
    """z_min == z_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, z_min=Decimal("3"), z_max=Decimal("3"))

    assert "ck_property_geometry_z_min_lt_z_max" in message


def test_z_min_greater_than_z_max_rejected(db_session, unit: Unit):
    """z_min > z_max is rejected by the CHECK constraint."""
    message = _assert_rejected(db_session, unit, z_min=Decimal("5"), z_max=Decimal("3"))

    assert "ck_property_geometry_z_min_lt_z_max" in message


def test_duplicate_unit_id_rejected(db_session, unit: Unit):
    """A second PropertyGeometry for the same unit is rejected by the UNIQUE constraint."""
    property_geometry_factory(db_session, unit)
    db_session.commit()

    now = datetime.now(timezone.utc)
    duplicate = PropertyGeometry(
        id=uuid4(),
        unit_id=unit.id,
        x_min=Decimal("10"),
        x_max=Decimal("20"),
        y_min=Decimal("5"),
        y_max=Decimal("10"),
        z_min=Decimal("3"),
        z_max=Decimal("6"),
        geometry_type="aabb",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(IntegrityError) as exc_info:
        with db_session.begin_nested():
            db_session.add(duplicate)
            db_session.flush()

    assert "uq_property_geometry_unit_id" in str(exc_info.value).lower()


def test_deleting_unit_cascades_to_property_geometry(db_session, unit: Unit):
    """Deleting a Unit cascade-deletes its PropertyGeometry."""
    geometry = property_geometry_factory(db_session, unit)
    db_session.commit()
    geometry_id = geometry.id

    assert db_session.get(PropertyGeometry, geometry_id) is not None

    db_session.delete(unit)
    db_session.commit()

    # expire_all() drops the identity-map copy, so get() reflects the database
    # rather than the still-cached in-memory object.
    db_session.expire_all()

    assert db_session.get(PropertyGeometry, geometry_id) is None

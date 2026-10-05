from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.validators.overlap_detector import detect_overlaps
from tests.integration.factories import property_geometry_factory, unit_factory

pytestmark = pytest.mark.integration


def test_detect_overlaps_loads_requested_geometries_from_database(db_session, floor):
    first = unit_factory(db_session, floor, unit_identifier="OVERLAP-A")
    second = unit_factory(
        db_session,
        floor,
        unit_identifier="OVERLAP-B",
        x_min=Decimal("2"),
        x_max=Decimal("8"),
        y_min=Decimal("1"),
        y_max=Decimal("4"),
        z_min=Decimal("1"),
        z_max=Decimal("2"),
    )
    first_geometry = property_geometry_factory(
        db_session,
        first,
        x_min=Decimal("0"),
        x_max=Decimal("5"),
        y_min=Decimal("0"),
        y_max=Decimal("3"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )
    second_geometry = property_geometry_factory(
        db_session,
        second,
        x_min=Decimal("2"),
        x_max=Decimal("8"),
        y_min=Decimal("1"),
        y_max=Decimal("4"),
        z_min=Decimal("1"),
        z_max=Decimal("2"),
    )

    results = detect_overlaps(
        [first_geometry.id, second_geometry.id, first_geometry.id],
        db=db_session,
    )

    assert len(results) == 1
    assert {results[0].unit_a_id, results[0].unit_b_id} == {first.id, second.id}
    assert results[0].overlap_volume == Decimal("6")
    assert results[0].overlap_geometry.model_dump() == {
        "x_min": Decimal("2"),
        "x_max": Decimal("5"),
        "y_min": Decimal("1"),
        "y_max": Decimal("3"),
        "z_min": Decimal("1"),
        "z_max": Decimal("2"),
    }


def test_detect_overlaps_reports_missing_geometry_ids(db_session):
    with pytest.raises(ValueError, match="Geometry not found"):
        detect_overlaps([uuid4()], db=db_session)

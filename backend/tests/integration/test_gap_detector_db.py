from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.validators.gap_detector import detect_gaps
from tests.integration.factories import property_geometry_factory, unit_factory

pytestmark = pytest.mark.integration


def test_detect_gaps_loads_geometry_and_returns_gap_results(db_session, floor):
    first = unit_factory(db_session, floor, unit_identifier="GAP-A")
    second = unit_factory(db_session, floor, unit_identifier="GAP-B")
    first_geometry = property_geometry_factory(
        db_session,
        first,
        x_min=Decimal("0"),
        x_max=Decimal("1"),
        y_min=Decimal("0"),
        y_max=Decimal("2"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )
    second_geometry = property_geometry_factory(
        db_session,
        second,
        x_min=Decimal("1.25"),
        x_max=Decimal("2.25"),
        y_min=Decimal("0"),
        y_max=Decimal("2"),
        z_min=Decimal("0"),
        z_max=Decimal("3"),
    )

    results = detect_gaps(
        [first_geometry.id, second_geometry.id],
        minimum_gap=Decimal("0.001"),
        maximum_gap=Decimal("1"),
        db=db_session,
    )

    assert len(results) == 1
    assert {results[0].unit_a_id, results[0].unit_b_id} == {first.id, second.id}
    assert results[0].gap_distance == Decimal("0.25")
    assert results[0].gap_direction == "x"


def test_detect_gaps_reports_missing_geometry_ids(db_session):
    with pytest.raises(ValueError, match="Geometry not found"):
        detect_gaps([uuid4()], db=db_session)

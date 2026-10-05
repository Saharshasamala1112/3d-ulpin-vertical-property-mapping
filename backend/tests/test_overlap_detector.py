from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest

from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.overlap import OverlapGeometry, OverlapResult
from app.validators.overlap_detector import _find_overlaps, detect_overlaps


def _geometry(
    *,
    unit_id: uuid.UUID | None = None,
    geometry_id: uuid.UUID | None = None,
    bounds: tuple[int, int, int, int, int, int] = (0, 10, 0, 10, 0, 10),
    geometry_type: GeometryType = GeometryType.AABB,
) -> PropertyGeometry:
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    return PropertyGeometry(
        id=geometry_id or uuid.uuid4(),
        unit_id=unit_id or uuid.uuid4(),
        x_min=Decimal(x_min),
        x_max=Decimal(x_max),
        y_min=Decimal(y_min),
        y_max=Decimal(y_max),
        z_min=Decimal(z_min),
        z_max=Decimal(z_max),
        geometry_type=geometry_type,
    )


def test_non_overlapping_geometries_return_empty_list():
    first = _geometry(bounds=(0, 1, 0, 1, 0, 1))
    second = _geometry(bounds=(1, 2, 0, 1, 0, 1))

    assert _find_overlaps([first, second]) == []


def test_partially_overlapping_geometries_report_exact_volume_and_bounds():
    unit_a, unit_b = uuid.uuid4(), uuid.uuid4()
    first = _geometry(unit_id=unit_a, bounds=(0, 4, 0, 4, 0, 4))
    second = _geometry(unit_id=unit_b, bounds=(2, 6, 1, 3, 3, 5))

    result = _find_overlaps([first, second])

    assert result == [
        OverlapResult(
            unit_a_id=min(unit_a, unit_b, key=str),
            unit_b_id=max(unit_a, unit_b, key=str),
            overlap_volume=Decimal("4"),
            overlap_geometry=OverlapGeometry(
                x_min=2,
                x_max=4,
                y_min=1,
                y_max=3,
                z_min=3,
                z_max=4,
            ),
        )
    ]


def test_fully_contained_geometry_reports_inner_box_volume():
    outer = _geometry(bounds=(0, 10, 0, 10, 0, 10))
    inner = _geometry(bounds=(2, 4, 3, 6, 1, 5))

    result = _find_overlaps([outer, inner])

    assert len(result) == 1
    assert result[0].overlap_volume == Decimal("24")
    assert result[0].overlap_geometry == OverlapGeometry(
        x_min=2,
        x_max=4,
        y_min=3,
        y_max=6,
        z_min=1,
        z_max=5,
    )


@pytest.mark.parametrize(
    "bounds",
    (
        (10, 11, 0, 1, 0, 1),
        (0, 1, 10, 11, 0, 1),
        (0, 1, 0, 1, 10, 11),
    ),
)
def test_edge_touching_geometries_are_not_overlaps(bounds):
    first = _geometry(bounds=(0, 10, 0, 10, 0, 10))
    second = _geometry(bounds=bounds)

    assert _find_overlaps([first, second]) == []


def test_multiple_overlaps_are_deterministic_and_input_order_independent():
    geometries = [
        _geometry(bounds=(0, 3, 0, 3, 0, 3)),
        _geometry(bounds=(1, 4, 1, 4, 1, 4)),
        _geometry(bounds=(2, 5, 2, 5, 2, 5)),
    ]

    forward = _find_overlaps(geometries)
    reverse = _find_overlaps(list(reversed(geometries)))

    assert forward == reverse
    assert len(forward) == 3


def test_duplicate_geometry_instances_for_same_unit_are_rejected():
    unit_id = uuid.uuid4()
    first = _geometry(unit_id=unit_id)
    second = _geometry(unit_id=unit_id)

    with pytest.raises(ValueError, match="same unit"):
        _find_overlaps([first, second])


def test_non_aabb_geometry_is_rejected():
    geometry = _geometry(geometry_type=GeometryType.POLYGON_3D)

    with pytest.raises(ValueError, match="only AABB"):
        _find_overlaps([geometry])


def test_invalid_geometry_is_rejected():
    geometry = _geometry(bounds=(0, 0, 0, 1, 0, 1))

    with pytest.raises(ValueError, match="invalid"):
        _find_overlaps([geometry])


def test_detect_overlaps_empty_input_does_not_open_database(monkeypatch):
    def fail_if_opened():
        raise AssertionError("empty ID list must not open a database session")

    monkeypatch.setattr("app.validators.overlap_detector.SessionLocal", fail_if_opened)

    assert detect_overlaps([]) == []


class _ScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return _ScalarResult(self.rows)


def test_detect_overlaps_queries_the_requested_geometry_ids():
    geometry = _geometry()

    result = detect_overlaps([geometry.id], db=_FakeSession([geometry]))

    assert result == []


def test_detect_overlaps_raises_when_requested_geometry_is_missing():
    with pytest.raises(ValueError, match="Geometry not found"):
        detect_overlaps([uuid.uuid4()], db=_FakeSession([]))


def test_detect_overlaps_opens_and_closes_an_application_session(monkeypatch):
    geometry = _geometry()

    class SessionContext(_FakeSession):
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

    session = SessionContext([geometry])
    monkeypatch.setattr("app.validators.overlap_detector.SessionLocal", lambda: session)

    assert detect_overlaps([geometry.id]) == []
    assert session.closed is True


def test_one_hundred_units_complete_within_one_second():
    geometries = [_geometry(bounds=(index * 2, index * 2 + 1, 0, 1, 0, 1)) for index in range(100)]

    started = time.perf_counter()
    result = _find_overlaps(geometries)
    elapsed = time.perf_counter() - started

    assert result == []
    assert elapsed < 1

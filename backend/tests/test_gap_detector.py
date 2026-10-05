from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest

from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.gap import GapGeometry, GapResult
from app.validators.gap_detector import _find_gaps, detect_gaps


def _geometry(
    *,
    unit_id: uuid.UUID | None = None,
    geometry_id: uuid.UUID | None = None,
    bounds: tuple[int | float, int | float, int | float, int | float, int | float, int | float] = (
        0,
        1,
        0,
        1,
        0,
        1,
    ),
    geometry_type: GeometryType = GeometryType.AABB,
) -> PropertyGeometry:
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    return PropertyGeometry(
        id=geometry_id or uuid.uuid4(),
        unit_id=unit_id or uuid.uuid4(),
        x_min=Decimal(str(x_min)),
        x_max=Decimal(str(x_max)),
        y_min=Decimal(str(y_min)),
        y_max=Decimal(str(y_max)),
        z_min=Decimal(str(z_min)),
        z_max=Decimal(str(z_max)),
        geometry_type=geometry_type,
    )


def test_perfectly_adjacent_units_have_no_gap():
    first = _geometry(bounds=(0, 1, 0, 1, 0, 1))
    second = _geometry(bounds=(1, 2, 0, 1, 0, 1))

    assert _find_gaps([first, second], Decimal("0.001"), Decimal("1")) == []


def test_gap_in_x_returns_distance_direction_and_region():
    unit_a, unit_b = uuid.uuid4(), uuid.uuid4()
    first = _geometry(unit_id=unit_a, bounds=(0, 1, 0, 2, 0, 3))
    second = _geometry(unit_id=unit_b, bounds=(1.25, 2.25, 0, 2, 0, 3))

    result = _find_gaps([first, second], Decimal("0.001"), Decimal("1"))

    assert result == [
        GapResult(
            unit_a_id=min(unit_a, unit_b, key=str),
            unit_b_id=max(unit_a, unit_b, key=str),
            gap_distance=Decimal("0.25"),
            gap_direction="x",
            gap_geometry=GapGeometry(
                x_min=1,
                x_max=Decimal("1.25"),
                y_min=0,
                y_max=2,
                z_min=0,
                z_max=3,
            ),
        )
    ]


@pytest.mark.parametrize(
    ("first_bounds", "second_bounds", "direction", "region"),
    (
        (
            (0, 1, 0, 1, 0, 1),
            (0, 1, 1.5, 2.5, 0, 1),
            "y",
            (0, 1, 1, Decimal("1.5"), 0, 1),
        ),
        (
            (0, 1, 0, 1, 0, 1),
            (0, 1, 0, 1, 2, 3),
            "z",
            (0, 1, 0, 1, 1, 2),
        ),
    ),
)
def test_gap_direction_is_detected_on_y_and_z(first_bounds, second_bounds, direction, region):
    result = _find_gaps(
        [_geometry(bounds=first_bounds), _geometry(bounds=second_bounds)],
        Decimal("0.001"),
        Decimal("1"),
    )

    assert len(result) == 1
    assert result[0].gap_direction == direction
    assert tuple(result[0].gap_geometry.model_dump().values()) == tuple(
        Decimal(str(value)) for value in region
    )


def test_edge_and_vertex_gap_returns_each_separated_axis():
    first = _geometry(bounds=(0, 1, 0, 1, 0, 1))
    second = _geometry(bounds=(1.2, 2.2, 1.3, 2.3, 1.4, 2.4))

    results = _find_gaps([first, second], Decimal("0.001"), Decimal("1"))

    assert [result.gap_direction for result in results] == ["x", "y", "z"]
    assert [result.gap_distance for result in results] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.4"),
    ]
    assert results[0].gap_geometry == GapGeometry(
        x_min=1,
        x_max=Decimal("1.2"),
        y_min=1,
        y_max=Decimal("1.3"),
        z_min=1,
        z_max=Decimal("1.4"),
    )
    assert all(result.gap_geometry == results[0].gap_geometry for result in results)


def test_minimum_and_maximum_gap_bounds_are_configurable():
    geometries = [
        _geometry(bounds=(0, 1, 0, 1, 0, 1)),
        _geometry(bounds=(1.1, 2.1, 0, 1, 0, 1)),
    ]

    assert _find_gaps(geometries, Decimal("0.1"), Decimal("1")) == []
    assert len(_find_gaps(geometries, Decimal("0.05"), Decimal("0.1"))) == 1
    assert _find_gaps(geometries, Decimal("0"), Decimal("0.09")) == []


def test_gaps_above_maximum_or_with_non_adjacent_units_are_ignored():
    first = _geometry(bounds=(0, 1, 0, 1, 0, 1))
    far_x = _geometry(bounds=(3, 4, 0, 1, 0, 1))
    far_y = _geometry(bounds=(0, 1, 3, 4, 0, 1))

    assert _find_gaps([first, far_x, far_y], Decimal("0"), Decimal("1")) == []


def test_multi_axis_pair_is_ignored_when_any_axis_exceeds_maximum():
    first = _geometry(bounds=(0, 1, 0, 1, 0, 1))
    second = _geometry(bounds=(1.2, 2.2, 1.3, 2.3, 3, 4))

    assert _find_gaps([first, second], Decimal("0"), Decimal("1")) == []


def test_multiple_pairs_return_deterministic_results():
    geometries = [
        _geometry(bounds=(0, 1, 0, 1, 0, 1)),
        _geometry(bounds=(1.5, 2.5, 0, 1, 0, 1)),
        _geometry(bounds=(3, 4, 0, 1, 0, 1)),
    ]

    forward = _find_gaps(geometries, Decimal("0"), Decimal("1"))
    reverse = _find_gaps(list(reversed(geometries)), Decimal("0"), Decimal("1"))

    assert forward == reverse
    assert len(forward) == 2


@pytest.mark.parametrize(
    ("minimum_gap", "maximum_gap"),
    (
        (-1, 1),
        (0, 0),
        (1, 1),
        (Decimal("NaN"), 1),
        (0, Decimal("Infinity")),
    ),
)
def test_invalid_tolerances_raise_value_error(minimum_gap, maximum_gap):
    with pytest.raises(ValueError):
        detect_gaps([], minimum_gap=minimum_gap, maximum_gap=maximum_gap)


def test_duplicate_geometries_for_one_unit_are_rejected():
    unit_id = uuid.uuid4()

    with pytest.raises(ValueError, match="same unit"):
        _find_gaps(
            [_geometry(unit_id=unit_id), _geometry(unit_id=unit_id)],
            Decimal("0"),
            Decimal("1"),
        )


def test_non_aabb_geometry_is_rejected():
    with pytest.raises(ValueError, match="only AABB"):
        _find_gaps(
            [_geometry(geometry_type=GeometryType.POLYGON_3D)],
            Decimal("0"),
            Decimal("1"),
        )


def test_invalid_geometry_is_rejected():
    with pytest.raises(ValueError, match="invalid"):
        _find_gaps([_geometry(bounds=(0, 0, 0, 1, 0, 1))], Decimal("0"), Decimal("1"))


def test_empty_ids_do_not_open_database(monkeypatch):
    monkeypatch.setattr(
        "app.validators.gap_detector.SessionLocal",
        lambda: pytest.fail("empty ID list must not open a database session"),
    )

    assert detect_gaps([]) == []


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


def test_detect_gaps_loads_requested_geometries_with_caller_session():
    first = _geometry()
    second = _geometry(bounds=(1.5, 2.5, 0, 1, 0, 1))

    results = detect_gaps([first.id, second.id], db=_FakeSession([first, second]))

    assert len(results) == 1
    assert results[0].gap_distance == Decimal("0.5")


def test_missing_geometry_id_is_reported():
    with pytest.raises(ValueError, match="Geometry not found"):
        detect_gaps([uuid.uuid4()], db=_FakeSession([]))


def test_detect_gaps_opens_and_closes_its_own_session(monkeypatch):
    first = _geometry()
    second = _geometry(bounds=(1.5, 2.5, 0, 1, 0, 1))

    class SessionContext(_FakeSession):
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

    session = SessionContext([first, second])
    monkeypatch.setattr("app.validators.gap_detector.SessionLocal", lambda: session)

    assert len(detect_gaps([first.id, second.id])) == 1
    assert session.closed


def test_one_hundred_units_complete_within_one_second():
    geometries = [_geometry(bounds=(index * 2, index * 2 + 1, 0, 1, 0, 1)) for index in range(100)]

    started = time.perf_counter()
    results = _find_gaps(geometries, Decimal("0.001"), Decimal("1"))
    elapsed = time.perf_counter() - started

    assert len(results) == 99
    assert elapsed < 1

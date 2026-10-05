from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.geometry3d import GeometryType, PropertyGeometry
from app.schemas.geometry3d import Geometry3DCreate
from app.services.geometry3d import get_geometry_by_unit, replace_geometry_for_unit


def _payload(**overrides) -> Geometry3DCreate:
    values = {
        "x_min": Decimal("1.123456"),
        "x_max": Decimal("5.654321"),
        "y_min": Decimal("2.5"),
        "y_max": Decimal("7.25"),
        "z_min": Decimal("0.1"),
        "z_max": Decimal("3.141593"),
        "geometry_type": "aabb",
    }
    return Geometry3DCreate(**(values | overrides))


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def first(self):
        return self.result


class _Session:
    def __init__(self, unit, geometry=None):
        self.unit = unit
        self.geometry = geometry
        self.added = []
        self.commit_count = 0
        self.refreshed = None

    def query(self, model):
        if model is PropertyGeometry:
            return _Query(self.geometry)
        return _Query(self.unit)

    def add(self, item):
        self.added.append(item)
        self.geometry = item

    def commit(self):
        self.commit_count += 1

    def refresh(self, item):
        self.refreshed = item


def _unit():
    return SimpleNamespace(id=uuid4())


def _geometry(unit_id):
    now = datetime.now(timezone.utc)
    return PropertyGeometry(
        id=uuid4(),
        unit_id=unit_id,
        x_min=Decimal("0"),
        x_max=Decimal("1"),
        y_min=Decimal("0"),
        y_max=Decimal("1"),
        z_min=Decimal("0"),
        z_max=Decimal("1"),
        geometry_type=GeometryType.AABB,
        created_at=now,
        updated_at=now,
    )


def test_get_geometry_returns_missing_geometry_error():
    session = _Session(_unit())

    with pytest.raises(ValueError, match="Geometry not found"):
        get_geometry_by_unit(session, str(session.unit.id))


def test_replace_geometry_creates_when_absent():
    unit = _unit()
    session = _Session(unit)

    result = replace_geometry_for_unit(session, str(unit.id), _payload())

    assert len(session.added) == 1
    assert result.unit_id == unit.id
    assert result.x_min == Decimal("1.123456")
    assert session.commit_count == 1
    assert session.refreshed is result


def test_replace_geometry_updates_existing_row():
    unit = _unit()
    geometry = _geometry(unit.id)
    session = _Session(unit, geometry)

    result = replace_geometry_for_unit(session, str(unit.id), _payload(x_max=Decimal("8.25")))

    assert result is geometry
    assert session.added == []
    assert result.x_max == Decimal("8.25")
    assert session.commit_count == 1


def test_replace_geometry_rejects_missing_unit():
    session = _Session(None)

    with pytest.raises(ValueError, match="Unit not found"):
        replace_geometry_for_unit(session, str(uuid4()), _payload())

    assert session.commit_count == 0

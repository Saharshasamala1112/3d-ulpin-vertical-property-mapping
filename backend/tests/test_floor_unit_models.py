import uuid
from decimal import Decimal

from sqlalchemy import Numeric

from app.models import (
    Building,
    BuildingType,
    ConstructionStatus,
    Floor,
    FloorType,
    Parcel,
    Unit,
    UnitStatus,
    UnitType,
)
from app.models.geometry3d import PropertyGeometry


def test_floor_imports_and_required_columns():
    assert {column.name for column in Floor.__table__.columns} == {
        "id",
        "building_id",
        "floor_number",
        "level_name",
        "floor_type",
        "elevation_min",
        "elevation_max",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }


def test_floor_type_values_are_exact():
    assert {item.value for item in FloorType} == {
        "basement",
        "ground",
        "typical",
        "penthouse",
        "rooftop",
    }


def test_floor_building_foreign_key_and_index():
    foreign_key = next(iter(Floor.__table__.c.building_id.foreign_keys))

    assert foreign_key.target_fullname == "buildings.id"
    assert foreign_key.ondelete == "CASCADE"
    assert "ix_floors_building_id" in {index.name for index in Floor.__table__.indexes}


def test_floor_elevation_fields_use_numeric():
    assert isinstance(Floor.__table__.c.elevation_min.type, Numeric)
    assert isinstance(Floor.__table__.c.elevation_max.type, Numeric)


def test_floor_relationships_use_back_populates():
    assert Floor.building.property.back_populates == "floors"
    assert Building.floors.property.back_populates == "building"


def test_floor_units_cascade_behavior():
    assert Floor.units.property.cascade.delete_orphan is True
    assert Floor.units.property.passive_deletes is True


def test_unit_imports_and_required_columns():
    assert {column.name for column in Unit.__table__.columns} == {
        "id",
        "floor_id",
        "unit_identifier",
        "unit_type",
        "area_sqm",
        "status",
        "vdc_code",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }


def test_unit_type_values_are_exact():
    assert {item.value for item in UnitType} == {
        "residential",
        "commercial",
        "parking",
        "storage",
        "common_area",
    }


def test_unit_status_values_are_exact():
    assert {item.value for item in UnitStatus} == {
        "planned",
        "active",
        "sold",
        "leased",
        "archived",
    }


def test_unit_floor_foreign_key_and_index():
    foreign_key = next(iter(Unit.__table__.c.floor_id.foreign_keys))

    assert foreign_key.target_fullname == "floors.id"
    assert foreign_key.ondelete == "CASCADE"
    assert "ix_units_floor_id" in {index.name for index in Unit.__table__.indexes}


def test_unit_measurement_fields_use_numeric():
    assert isinstance(Unit.__table__.c.area_sqm.type, Numeric)


def test_unit_has_no_duplicate_bounding_box_columns():
    assert not {
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "z_min",
        "z_max",
    } & {column.name for column in Unit.__table__.columns}
    assert {
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "z_min",
        "z_max",
    } <= {column.name for column in PropertyGeometry.__table__.columns}


def test_unit_vdc_code_is_nullable():
    assert Unit.__table__.c.vdc_code.nullable is True


def test_unit_relationships_use_back_populates():
    assert Unit.floor.property.back_populates == "units"
    assert Floor.units.property.back_populates == "floor"


def test_building_can_have_multiple_floors_at_orm_level():
    parcel = Parcel(
        id=uuid.uuid4(),
        parcel_identifier="P-1",
        ulpin="U-1",
        geometry=None,
        area_sqm=100.0,
    )
    building = Building(
        building_identifier="B-1",
        building_type=BuildingType.RESIDENTIAL,
        construction_status=ConstructionStatus.COMPLETED,
    )
    parcel.buildings.append(building)

    first = Floor(
        floor_number=1,
        floor_type=FloorType.GROUND,
        elevation_min=Decimal("0"),
        elevation_max=Decimal("3"),
    )
    second = Floor(
        floor_number=2,
        floor_type=FloorType.TYPICAL,
        elevation_min=Decimal("3"),
        elevation_max=Decimal("6"),
    )

    building.floors.extend([first, second])

    assert first.building is building
    assert second.building is building
    assert len(building.floors) == 2


def test_floor_can_have_multiple_units_at_orm_level():
    floor = Floor(
        building_id=uuid.uuid4(),
        floor_number=1,
        floor_type=FloorType.GROUND,
        elevation_min=Decimal("0"),
        elevation_max=Decimal("3"),
    )

    first = Unit(
        unit_identifier="U-1",
        unit_type=UnitType.RESIDENTIAL,
        area_sqm=Decimal("50"),
        status=UnitStatus.PLANNED,
    )
    second = Unit(
        unit_identifier="U-2",
        unit_type=UnitType.COMMERCIAL,
        area_sqm=Decimal("80"),
        status=UnitStatus.ACTIVE,
    )

    floor.units.extend([first, second])

    assert first.floor is floor
    assert second.floor is floor
    assert len(floor.units) == 2

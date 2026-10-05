import uuid

from app.models import Building, BuildingType, ConstructionStatus, Parcel


def test_building_imports_and_required_columns():
    assert {column.name for column in Building.__table__.columns} == {
        "id",
        "parcel_id",
        "building_identifier",
        "name",
        "building_type",
        "construction_status",
        "footprint_geometry",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }


def test_building_enum_values_are_exact():
    assert {item.value for item in BuildingType} == {
        "residential",
        "commercial",
        "mixed_use",
        "industrial",
        "institutional",
    }
    assert {item.value for item in ConstructionStatus} == {
        "planned",
        "under_construction",
        "completed",
        "demolished",
    }


def test_building_parcel_foreign_key_and_index():
    foreign_key = next(iter(Building.__table__.c.parcel_id.foreign_keys))

    assert foreign_key.target_fullname == "parcels.id"
    assert foreign_key.ondelete == "CASCADE"
    assert "ix_buildings_parcel_id" in {index.name for index in Building.__table__.indexes}


def test_building_geometry_is_nullable_polygon_wgs84():
    geometry = Building.__table__.c.footprint_geometry

    assert geometry.nullable is True
    assert geometry.type.geometry_type == "POLYGON"
    assert geometry.type.srid == 4326


def test_building_relationships_use_back_populates():
    assert Building.parcel.property.back_populates == "buildings"
    assert Parcel.buildings.property.back_populates == "parcel"


def test_parcel_can_have_multiple_buildings_at_orm_level():
    parcel = Parcel(
        id=uuid.uuid4(),
        parcel_identifier="P-1",
        ulpin="U-1",
        geometry=None,
        area_sqm=100.0,
    )
    first = Building(
        building_identifier="B-1",
        building_type=BuildingType.RESIDENTIAL,
        construction_status=ConstructionStatus.COMPLETED,
    )
    second = Building(
        building_identifier="B-2",
        building_type=BuildingType.COMMERCIAL,
        construction_status=ConstructionStatus.PLANNED,
    )

    parcel.buildings.extend([first, second])

    assert first.parcel is parcel
    assert second.parcel is parcel
    assert len(parcel.buildings) == 2


def test_building_identifier_has_no_false_global_uniqueness_constraint():
    # Project scope is not represented in the current schema, so no uniqueness
    # constraint can be enforced without inventing a project relationship.
    assert Building.__table__.c.building_identifier.unique is not True
    assert not any(
        constraint.columns.keys() == ["building_identifier"]
        for constraint in Building.__table__.constraints
        if hasattr(constraint, "columns")
    )

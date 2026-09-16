from app.models.parcel import Parcel, ParcelStatus, ULPIN


def test_parcel_model_contract():
    parcel_columns = {column.name for column in Parcel.__table__.columns}

    assert "id" in parcel_columns
    assert "parcel_identifier" in parcel_columns
    assert "ulpin" in parcel_columns
    assert "geometry" in parcel_columns
    assert "area_sqm" in parcel_columns
    assert "status" in parcel_columns
    assert "metadata" in parcel_columns
    assert "created_at" in parcel_columns
    assert "updated_at" in parcel_columns

    assert Parcel.__table__.c.parcel_identifier.unique is True
    assert Parcel.__table__.c.ulpin.unique is True
    assert "ix_parcels_ulpin" in {index.name for index in Parcel.__table__.indexes}
    assert Parcel.__table__.c.geometry.type.geometry_type == "MULTIPOLYGON"
    assert Parcel.__table__.c.geometry.type.srid == 4326


def test_ulpin_model_contract():
    ulpin_columns = {column.name for column in ULPIN.__table__.columns}

    assert "id" in ulpin_columns
    assert "parcel_id" in ulpin_columns
    assert "ulpin_code" in ulpin_columns
    assert "issued_date" in ulpin_columns
    assert "issuing_authority" in ulpin_columns
    assert "checksum" in ulpin_columns

    assert ULPIN.__table__.c.ulpin_code.unique is True


def test_parcel_status_values():
    assert {status.value for status in ParcelStatus} == {
        "draft",
        "registered",
        "active",
        "archived",
    }

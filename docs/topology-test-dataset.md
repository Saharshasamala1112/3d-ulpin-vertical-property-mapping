# Deterministic 3D Topology Validation Dataset

The seeded topology dataset provides repeatable PostgreSQL/PostGIS records for
the building and unit validation endpoints. Entity IDs are generated with UUIDv5
from stable scenario names, and `seed_topology_dataset` uses ORM merges so the
seed can be run repeatedly without creating duplicate rows.

## Scenarios

| Scenario | Expected result |
|----------|-----------------|
| `valid` | One valid unit; the report passes with no findings. |
| `overlap` | Two units overlap with positive intersection volume. |
| `gap` | Two units have a 0.2-unit gap on the x axis. |
| `elevation` | Reports inconsistent unit elevations, overlapping floors, a unit spanning floors, and a unit outside its floor. |
| `invalid-geometry` | A persisted `polygon_3d` is reported as `UNSUPPORTED_GEOMETRY_TYPE`. |
| `missing-geometry` | A unit without a geometry row is reported as `MISSING_GEOMETRY`. |
| `mixed` | One report contains geometry, overlap, gap, and elevation findings. |

The geometry validator's `INVALID_DIMENSIONS`, `ZERO_VOLUME`, and
`DIMENSION_BELOW_THRESHOLD` codes are exercised using the deterministic input
examples in `backend/tests/fixtures/topology_dataset.py`. They are not stored as
database rows: the `property_geometry` check constraints intentionally reject
inverted and zero-size bounds, while the minimum-dimension rule is a validation
policy rather than a persistence constraint.

## Seed a dedicated test database

From `backend/`, set `TEST_DATABASE_URL` to a disposable PostgreSQL database
with PostGIS access, then run:

```bash
TEST_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/geosix_test' \
  python alembic/seed_topology_dataset.py
```

The script applies Alembic migrations to that database before seeding. It refuses
to run unless `TEST_DATABASE_URL` is set; it never seeds the application's
default or production database URL.

Run the API integration coverage against the same migrated test database with:

```bash
TEST_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/geosix_test' \
  pytest tests/integration/test_topology_dataset.py
```

Each integration test runs inside the repository's transaction-isolated test
fixture and rolls back its seeded rows at teardown.

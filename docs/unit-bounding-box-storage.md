# Canonical Unit Bounding Boxes

`property_geometry` is the single authoritative store for every unit's 3D
axis-aligned bounding box. The `units` table no longer stores a second copy.
Geometry validation, overlap and gap detection, elevation validation, and the
unit geometry API all read the canonical geometry record.

## API compatibility and validation

The unit create and update payloads retain their existing `x_min`, `x_max`,
`y_min`, `y_max`, `z_min`, and `z_max` fields. Unit responses continue returning
those fields, derived from `property_geometry`. Creating a unit creates its
canonical geometry in the same transaction; updating any bounds through the
unit API updates that same geometry record. The geometry endpoint can also
replace the record and its derived measurements.

All six coordinates must fit the canonical numeric precision (18 digits, with
up to 6 decimal places). Each axis must satisfy **strictly**
`min < max`. Equality was previously accepted by unit create/update validation;
zero-size dimensions are now rejected consistently by the unit API, geometry
API, and database constraints. This is a deliberate validation tightening;
the request and response field shapes remain compatible.

## Migration and existing records

Alembic revision `0005_unify_unit_property_geometry` backfills missing
`property_geometry` records from the previous `units` columns, preserves the
unit's timestamps, verifies row counts and coordinate equality, and then drops
the duplicate columns. Its downgrade restores the columns from the canonical
geometry values.

The upgrade does not silently discard conflicting data. Before changing the
schema it aborts with the affected unit IDs if existing copies disagree,
coordinates have zero/inverted dimensions, or values cannot fit the canonical
numeric precision without rounding. Reconcile those rows before retrying the
migration; the original unit columns remain in place when these preflight
checks fail.

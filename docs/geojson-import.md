# GeoJSON Data Import

GeoJSON import supports synchronous onboarding of parcel boundaries and building
footprints. Both endpoints accept a `FeatureCollection`, validate features
independently, and return one result per input feature.

## Limits and transaction behavior

- Maximum request body: **10 MiB**.
- Maximum collection size: **500 features**.
- The complete request is held in memory while it is validated and imported;
  memory use is bounded by the request-size cap.
- Each feature is written inside its own PostgreSQL savepoint. A failed feature
  is rolled back without stopping later features. Successful features are
  committed together after the collection has been processed.
- Requests are synchronous. Queued imports, streaming progress, and geometry
  repair are out of scope.
- Dry-run is the default and performs no writes. The report classifies each
  feature against the current database so the preview can be compared to the
  confirmed run.

## Parcel import

`POST /api/v1/parcels/import?dry_run=true`

The ULPIN property defaults to `ulpin` and can be selected with the
`ulpin_property` query parameter. ULPIN must follow the existing GEOSIX format:
`GEOSX` followed by exactly five digits. Each feature requires
`parcel_identifier` (or `name`) and a finite, positive `area_sqm`. Optional
properties are `status` and an object-valued `metadata`. Status values are
`draft`, `registered`, `active`, or `archived`.

Parcel geometry must be a valid two-dimensional Polygon or MultiPolygon in
longitude/latitude (SRID 4326). Polygon inputs are stored as MultiPolygon to
match the parcel table's geometry type.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "ulpin": "GEOSX00001",
        "parcel_identifier": "PARCEL-001",
        "area_sqm": 1200,
        "status": "active"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]]
      }
    }
  ]
}
```

An existing parcel with the same ULPIN is updated when its imported values
differ; an identical feature is skipped. A `parcel_identifier` already used by
a different ULPIN fails that feature without aborting the batch.

## Building import

`POST /api/v1/buildings/import?dry_run=true`

Building features require `building_identifier` (or `name`) and a Polygon
footprint. Set `parcel_id` in feature properties or supply a default target
parcel with the request-level `parcel_id` query parameter. The parent parcel
must exist. Optional `building_type` and `construction_status` values default
to `residential` and `planned` and follow the existing Building API enums.
Buildings are upserted by `(parcel_id, building_identifier)`; floors and units
remain managed by their existing APIs.

## Report

Each response contains batch counts and feature outcomes:

```json
{
  "dry_run": true,
  "created": 1,
  "updated": 0,
  "skipped": 0,
  "failed": 1,
  "features": [
    {
      "index": 1,
      "status": "created",
      "key": "GEOSX00001",
      "record_id": null,
      "reason": null
    },
    {
      "index": 2,
      "status": "failed",
      "key": "invalid",
      "record_id": null,
      "reason": "ULPIN must be GEOSX followed by exactly 5 digits."
    }
  ]
}
```

`created`, `updated`, and `skipped` outcomes are descriptive during dry-run;
`record_id` is populated only when an existing record is identified. A confirmed
run uses the same validation and reports persisted record IDs.

Both endpoints require the `editor` role or higher. Reader requests receive
`403`; the Parcels screen provides an editor-only file picker, preview,
per-feature report, and explicit confirmation step.

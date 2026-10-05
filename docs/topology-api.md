# 3D Topology Validation API

The topology endpoints are read-only and return a common
`TopologyValidationReport`. `summary.status` is `passed` only when every
applicable geometry, overlap, gap, and elevation check passes. Missing,
invalid, or unsupported geometry is reported with its unit ID and excluded from
pairwise checks so one bad geometry does not hide other findings. IDs that
refer to nonexistent buildings or units return the standard `NOT_FOUND` error.

## Building validation

```http
POST /api/v1/topology/validate/building/{building_id}
```

Validates all units in the building, including geometry quality, pairwise AABB
overlaps and gaps, and floor/unit elevation consistency. The default gap range
is `0.001 < distance <= 1` coordinate units.

## Single-unit validation

```http
POST /api/v1/topology/validate/unit/{unit_id}
```

Validates one unit's associated 3D property geometry independently.

## Pairwise overlap check

```http
POST /api/v1/topology/validate/overlaps
Content-Type: application/json

{"unit_ids": ["<uuid>", "<uuid>"]}
```

## Pairwise gap check

```http
POST /api/v1/topology/validate/gaps
Content-Type: application/json

{
  "unit_ids": ["<uuid>", "<uuid>"],
  "minimum_gap": 0.001,
  "maximum_gap": 1
}
```

`minimum_gap` and `maximum_gap` are optional and use the detector defaults when
omitted. The maximum must be greater than the minimum. Gaps are reported when
`minimum_gap < gap_distance <= maximum_gap`.

Pairwise request IDs are unit IDs, not geometry IDs. Units without valid AABB
geometry appear in `geometry_errors`; checks are performed on the remaining
valid geometries. An empty `unit_ids` list returns a successful empty report.

## Response shape

```json
{
  "summary": {
    "status": "failed",
    "valid": false,
    "geometry_error_count": 0,
    "overlap_count": 1,
    "gap_count": 0,
    "elevation_error_count": 0
  },
  "geometry_errors": [],
  "overlap_results": [],
  "gap_results": [],
  "elevation_errors": []
}
```

FastAPI publishes request/response and error schemas at `/docs` and
`/openapi.json`. The orchestrator shares one database session across the
checks; database operations are intentionally sequential because SQLAlchemy
sessions are not safe for concurrent use.

An in-memory Python 3.14 benchmark of geometry validation plus both pairwise
detectors averaged `3.67 ms` per 100 spatially separated geometries over 1,000
runs. A PostGIS-backed end-to-end integration test also asserts the building
endpoint completes in under five seconds for 100 units; database query and
deployment latency are included in that CI acceptance check.

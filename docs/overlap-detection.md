# 3D Volumetric Overlap Detection

`app.validators.overlap_detector.detect_overlaps` loads the requested
`PropertyGeometry` records and returns every positive-volume AABB intersection:

```python
from app.validators.overlap_detector import detect_overlaps

overlaps = detect_overlaps([geometry_id_a, geometry_id_b])
```

Pass an existing SQLAlchemy session with `db=` when running within a request,
transaction, or test. Without it, the function opens and closes its own session.
An empty ID list returns immediately. Repeated IDs are deduplicated; unknown IDs,
multiple geometry records for one unit, invalid geometry, or unsupported
non-AABB geometry raise `ValueError` rather than silently producing incomplete
results.

Each Pydantic `OverlapResult` includes `unit_a_id`, `unit_b_id`,
`overlap_volume`, and `overlap_geometry`, whose six Decimal fields describe the
intersection AABB. Unit IDs are ordered consistently, and results are sorted by
unit IDs so output is deterministic regardless of input or query order.
Intersections must have positive extent on all three axes; face-, edge-, and
point-touching boxes are not overlaps.

The detector sorts boxes by their X minimum and sweeps forward, expiring boxes
whose X maximum no longer intersects the current box. Only active X candidates
are then checked for strict Y and Z interval intersection. This sort-and-sweep
approach is `O(n log n + c)`, where `c` is the number of active-X candidate
checks (quadratic in the densest worst case, as can be the output itself).

For 100 spatially disjoint boxes, a local Python 3.14 `timeit` benchmark over
1,000 runs averaged `2.18 ms` per detection, below the one-second acceptance
limit. The benchmark measures the in-memory sweep-and-prune phase; database
loading is separate.

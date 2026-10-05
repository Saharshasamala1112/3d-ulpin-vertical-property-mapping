# 3D Spatial Gap Detection

`app.validators.gap_detector.detect_gaps` loads the requested
`PropertyGeometry` records and returns Pydantic `GapResult` values:

```python
from app.validators.gap_detector import detect_gaps

gaps = detect_gaps(
    [geometry_id_a, geometry_id_b],
    minimum_gap=0.001,
    maximum_gap=1.0,
)
```

Coordinates and thresholds use the same units as the geometry (meters in the
current model). Defaults ignore gaps of `0.001` units or less and report
candidate adjacency gaps up to and including `1.0` unit. Set both
`minimum_gap` and `maximum_gap` per run to configure the accepted range; the
maximum must be strictly greater than the minimum. Gaps are reported only when
`minimum_gap < gap_distance <= maximum_gap`. The maximum also prevents distant
units from being misclassified as adjacent.

When units are separated on multiple axes (edge- or vertex-style adjacency),
the detector returns one result per separated axis. Each result contains the
axis-specific distance and direction; all results for that pair carry the same
`gap_geometry`, the AABB between the facing boundaries and their shared
projection. Perfect contact has zero distance and is not a gap. An empty ID list
returns immediately; missing IDs, invalid AABBs, duplicate geometries for a
unit, and unsupported non-AABB geometries raise `ValueError`.

Pass an existing SQLAlchemy session with `db=` to participate in a caller-owned
transaction. Otherwise the detector opens and closes its own session.

The detector sorts by X minimum and sweeps forward, expiring boxes more than
`maximum_gap` behind the current box. Remaining candidate pairs are checked on
all three axes. Runtime is `O(n log n + c)`, where `c` is the number of active-X
candidate pairs (quadratic in a densely packed worst case). A Python 3.14
benchmark over 1,000 runs for 100 adjacent boxes averaged `4.21 ms` per
detection, well below the one-second per-building requirement. This measures the
in-memory sweep-and-prune step; database loading is separate.

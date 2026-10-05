# 3D Geometry Validation

`app.validators.geometry3d_validator.validate_geometry` validates a
`PropertyGeometry` ORM object or a `GeometryValidationInput` Pydantic model. It
does not modify the input or access external services.

```python
from app.validators.geometry3d_validator import validate_geometry

result = validate_geometry(geometry, minimum_dimension=0.01)
result.model_dump()
```

The default minimum dimension is `0.001` coordinate units (one millimeter when
coordinates are in meters). Set `minimum_dimension` for an individual call to
apply a different non-negative threshold. Invalid thresholds raise `ValueError`.

Results have the following shape:

```json
{
  "valid": false,
  "errors": [
    {
      "code": "DIMENSION_BELOW_THRESHOLD",
      "message": "X dimension 0.0005 is below the minimum dimension 0.001.",
      "field": "x"
    }
  ],
  "warnings": []
}
```

Each error contains a stable code, human-readable message, and coordinate field.
`MISSING_GEOMETRY` reports a null geometry or missing bounding-box coordinate;
`INVALID_DIMENSIONS` reports inverted or non-finite coordinates; `ZERO_VOLUME`
reports an axis with no extent or a non-positive volume; and
`DIMENSION_BELOW_THRESHOLD` reports a positive axis extent below the configured
minimum. Warnings are included in the response contract and are empty unless
warning rules are introduced.

Validation performs a fixed number of Decimal comparisons and multiplications,
so runtime is constant for a single bounding box. A local Python 3.14 `timeit`
benchmark over 10,000 validations averaged `0.0063 ms` per call (about `6.3 µs`),
below the 10 ms single-geometry acceptance limit.

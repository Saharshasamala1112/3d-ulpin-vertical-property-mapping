/**
 * Client-side GeoJSON validation.
 *
 * The backend only validates that `geometry` / `footprint_geometry` is a dict
 * (`dict[str, Any]` in `backend/app/schemas/parcel.py`). It then passes the
 * value to PostGIS `ST_GeomFromGeoJSON`
 * (`backend/app/services/parcel.py::_insert_geometry`), which raises a
 * database error on malformed *content*.
 *
 * That error is unhandled, so it falls through to the generic handler in
 * `backend/app/main.py` and the client receives a bare
 * 500 / `INTERNAL_ERROR` / "Internal server error" with no field attribution.
 *
 * Because of that, structural validation has to happen here so the user gets a
 * field-level message instead of a generic server error.
 *
 * Deliberately conservative: this does NOT enforce a geometry `type` whitelist,
 * because the API does not enforce one either and over-constraining would
 * reject payloads the server accepts. It DOES walk the `coordinates` array
 * recursively, because that is the layer the server never inspects and where
 * the opaque 500 actually originates.
 */

/** Nesting depth expected for each geometry `type`, or `null` if unknown. */
const REQUIRED_DEPTH: Record<string, number> = {
  Point: 0,
  MultiPoint: 1,
  LineString: 1,
  MultiLineString: 2,
  Polygon: 2,
  MultiPolygon: 3,
};

/**
 * A GeoJSON position is 2-3 finite numbers, and every nesting level below the
 * geometry must be a non-empty array. Mixed-depth trees (`[[[0,0]], [1,1]]`)
 * are the common paste error and are what PostGIS chokes on.
 */
function isPositionArray(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    value.length <= 3 &&
    value.every((item) => typeof item === 'number' && Number.isFinite(item))
  );
}

function checkCoordinates(value: unknown, depth: number, path: string): string | null {
  if (depth === 0) {
    return isPositionArray(value)
      ? null
      : `${path} must be a position of 2 or 3 finite numbers, e.g. [12.9716, 77.5946].`;
  }
  if (!Array.isArray(value) || value.length === 0) {
    return `${path} must be a non-empty array${depth > 1 ? ' of nested arrays' : ''}.`;
  }
  for (let index = 0; index < value.length; index += 1) {
    const problem = checkCoordinates(value[index], depth - 1, `${path}[${index}]`);
    if (problem) return problem;
  }
  return null;
}

export interface GeoJsonParseSuccess {
  ok: true;
  value: Record<string, unknown>;
}

export interface GeoJsonParseFailure {
  ok: false;
  error: string;
}

export type GeoJsonParseResult = GeoJsonParseSuccess | GeoJsonParseFailure;

/** Parse raw pasted text into a GeoJSON geometry object. */
export function parseGeoJsonText(text: string): GeoJsonParseResult {
  const trimmed = text.trim();
  if (!trimmed) {
    return { ok: false, error: 'Geometry is required.' };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return { ok: false, error: `Invalid JSON: ${detail}` };
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return {
      ok: false,
      error: 'Geometry must be a JSON object, not an array or a primitive value.',
    };
  }

  const geometry = parsed as Record<string, unknown>;

  if (typeof geometry.type !== 'string' || !geometry.type) {
    return { ok: false, error: 'Geometry must include a non-empty "type" string.' };
  }

  if (!('coordinates' in geometry)) {
    return { ok: false, error: 'Geometry must include a "coordinates" property.' };
  }

  if (!Array.isArray(geometry.coordinates)) {
    return { ok: false, error: 'Geometry "coordinates" must be an array.' };
  }

  // Walk the tree for every type we know the depth of. Unknown types (e.g. a
  // GeometryCollection, which nests `geometries` rather than `coordinates`)
  // keep the older structure-only behaviour instead of being rejected.
  const expectedDepth = REQUIRED_DEPTH[geometry.type];
  if (expectedDepth !== undefined) {
    const problem = checkCoordinates(geometry.coordinates, expectedDepth, 'Geometry "coordinates"');
    if (problem) return { ok: false, error: problem };
  }

  return { ok: true, value: geometry };
}

/** Pretty-print a geometry object for editing, tolerating empty input. */
export function stringifyGeoJson(value: unknown): string {
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

/** A minimal valid MultiPolygon, offered as a starting point in the form. */
export const MULTI_POLYGON_TEMPLATE = {
  type: 'MultiPolygon',
  coordinates: [
    [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 0],
      ],
    ],
  ],
} as const;

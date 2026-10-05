/**
 * Types for the 3D property geometry viewer.
 *
 * The W28 geometry API stores coordinates as `Numeric(18, 6)` columns, which
 * Pydantic serialises as JSON *strings* (e.g. `"1.123456"`). `GeometryWire`
 * models that wire format verbatim; `toUnitGeometry` is the only place in the
 * app where those strings become numbers. Everything downstream works with the
 * `UnitGeometry` read model.
 */

export type GeometryType = 'aabb';

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/** Axis-aligned bounding box in the building's local metric frame, in metres. */
export interface UnitAabb {
  min: Vec3;
  max: Vec3;
}

/** Raw `/api/v1/units/{unit_id}/geometry` payload. All numbers are strings. */
export interface GeometryWire {
  id: string;
  unit_id: string;
  x_min: string;
  x_max: string;
  y_min: string;
  y_max: string;
  z_min: string;
  z_max: string;
  geometry_type: GeometryType;
  created_at: string;
  updated_at: string;
  volume: string;
  centroid: [string, string, string];
  dimensions: [string, string, string];
}

/** Converted geometry, ready for rendering. */
export interface UnitGeometry {
  id: string;
  unitId: string;
  geometryType: GeometryType;
  bounds: UnitAabb;
  centroid: Vec3;
  dimensions: Vec3;
  volume: number;
  createdAt: string;
  updatedAt: string;
}

export interface ParcelOption {
  id: string;
  identifier: string;
  ulpin: string;
}

export interface BuildingOption {
  id: string;
  identifier: string;
  name: string;
  buildingType: string;
  constructionStatus: string;
}

export interface FloorSummary {
  id: string;
  floorNumber: number;
  levelName: string;
  floorType: string;
}

export interface UnitSummary {
  id: string;
  unitIdentifier: string;
  unitType: string;
  status: string;
}

export interface SceneUnit {
  id: string;
  unitIdentifier: string;
  unitType: string;
  status: string;
  floor: FloorSummary;
  geometry: UnitGeometry;
}

export interface UnitWithoutGeometry {
  id: string;
  unitIdentifier: string;
  floor: FloorSummary;
}

/** Everything the viewer needs for one building. */
export interface BuildingScene {
  building: BuildingOption;
  floors: FloorSummary[];
  units: SceneUnit[];
  unitsWithoutGeometry: UnitWithoutGeometry[];
}

function toNumber(value: string, field: string): number {
  // `Number('')` is 0 and `Number(' ')` is 0, so a blank string would
  // otherwise slip through and collapse a bounding box to the origin.
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Geometry field "${field}" is not a number: ${JSON.stringify(value)}`);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Geometry field "${field}" is not a number: ${JSON.stringify(value)}`);
  }
  return parsed;
}

function toVec3(tuple: [string, string, string], field: string): Vec3 {
  return {
    x: toNumber(tuple[0], `${field}.x`),
    y: toNumber(tuple[1], `${field}.y`),
    z: toNumber(tuple[2], `${field}.z`),
  };
}

/**
 * The single API-boundary conversion: wire strings -> numbers.
 *
 * `centroid`, `dimensions` and `volume` are used straight from the API rather
 * than recomputed, so the render never drifts from what the server reports.
 */
export function toUnitGeometry(wire: GeometryWire): UnitGeometry {
  return {
    id: wire.id,
    unitId: wire.unit_id,
    geometryType: wire.geometry_type,
    bounds: {
      min: { x: toNumber(wire.x_min, 'x_min'), y: toNumber(wire.y_min, 'y_min'), z: toNumber(wire.z_min, 'z_min') },
      max: { x: toNumber(wire.x_max, 'x_max'), y: toNumber(wire.y_max, 'y_max'), z: toNumber(wire.z_max, 'z_max') },
    },
    centroid: toVec3(wire.centroid, 'centroid'),
    dimensions: toVec3(wire.dimensions, 'dimensions'),
    volume: toNumber(wire.volume, 'volume'),
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  };
}

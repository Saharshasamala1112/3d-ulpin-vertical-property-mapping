import { apiClient } from './api-client';
import {
  toUnitGeometry,
  type BuildingOption,
  type BuildingScene,
  type FloorSummary,
  type GeometryWire,
  type ParcelOption,
  type SceneUnit,
  type UnitSummary,
  type UnitWithoutGeometry,
} from '../types/geometry';

const API = '/api/v1';
const PARCEL_PAGE_SIZE = 100;

/**
 * `apiClient` rejects with `{ status, data }`. The geometry endpoints answer
 * with `{ error_code, message, details }` while some older endpoints nest the
 * code under `error`, so both shapes are unwrapped here.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function isNotFoundError(error: unknown): boolean {
  return isRecord(error) && error.status === 404;
}

export function toErrorMessage(error: unknown, fallback: string): string {
  if (!isRecord(error)) return fallback;
  const data = error.data;
  if (typeof data === 'string') return data;
  if (!isRecord(data)) return fallback;
  if (typeof data.message === 'string') return data.message;
  if (isRecord(data.error) && typeof data.error.message === 'string') return data.error.message;
  return fallback;
}

interface ParcelFeatureWire {
  type: 'Feature';
  id: string;
  properties: {
    id: string;
    parcel_identifier: string;
    ulpin: string;
  };
}

interface ParcelListWire {
  data: ParcelFeatureWire[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export async function listParcels(): Promise<ParcelOption[]> {
  const response = await apiClient.get<ParcelListWire>(
    `${API}/parcels?page=1&per_page=${PARCEL_PAGE_SIZE}`,
  );
  return response.data.map((feature) => ({
    id: feature.properties.id,
    identifier: feature.properties.parcel_identifier,
    ulpin: feature.properties.ulpin,
  }));
}

interface BuildingWire {
  id: string;
  building_identifier: string;
  name: string;
  building_type: string;
  construction_status: string;
}

export async function listBuildings(parcelId: string): Promise<BuildingOption[]> {
  const response = await apiClient.get<BuildingWire[]>(`${API}/parcels/${parcelId}/buildings`);
  return response.map((building) => ({
    id: building.id,
    identifier: building.building_identifier,
    name: building.name,
    buildingType: building.building_type,
    constructionStatus: building.construction_status,
  }));
}

interface FloorWire {
  id: string;
  floor_number: number;
  level_name: string;
  floor_type: string;
}

export async function listFloors(buildingId: string): Promise<FloorSummary[]> {
  const response = await apiClient.get<FloorWire[]>(`${API}/buildings/${buildingId}/floors`);
  return response.map((floor) => ({
    id: floor.id,
    floorNumber: floor.floor_number,
    levelName: floor.level_name,
    floorType: floor.floor_type,
  }));
}

interface UnitWire {
  id: string;
  unit_identifier: string;
  unit_type: string;
  status: string;
}

export async function listUnits(floorId: string): Promise<UnitSummary[]> {
  const response = await apiClient.get<UnitWire[]>(`${API}/floors/${floorId}/units`);
  return response.map((unit) => ({
    id: unit.id,
    unitIdentifier: unit.unit_identifier,
    unitType: unit.unit_type,
    status: unit.status,
  }));
}

/**
 * Fetch one unit's bounding box, or `null` when the unit has none.
 *
 * A unit without geometry is a normal state, not an error, so 404 is folded
 * into `null` here and only real failures propagate.
 */
export async function getUnitGeometry(unitId: string) {
  try {
    const wire = await apiClient.get<GeometryWire>(`${API}/units/${unitId}/geometry`);
    return toUnitGeometry(wire);
  } catch (error) {
    if (isNotFoundError(error)) return null;
    throw error;
  }
}

interface ResolvedUnit {
  unit: UnitSummary;
  floor: FloorSummary;
  geometry: Awaited<ReturnType<typeof getUnitGeometry>>;
}

/**
 * Build the full viewer model for a building.
 *
 * The W28 API exposes geometry per unit, so this walks the existing
 * parcel -> building -> floors -> units hierarchy and then resolves each
 * unit's box. Levels are fetched concurrently; the per-unit lookups are
 * bounded by how many units a building has.
 */
export async function loadBuildingScene(building: BuildingOption): Promise<BuildingScene> {
  const floors = await listFloors(building.id);

  const withUnits = await Promise.all(
    floors.map(async (floor) => ({ floor, units: await listUnits(floor.id) })),
  );

  const resolved: ResolvedUnit[] = await Promise.all(
    withUnits.flatMap(({ floor, units }) =>
      units.map(async (unit) => ({ unit, floor, geometry: await getUnitGeometry(unit.id) })),
    ),
  );

  const units: SceneUnit[] = [];
  const unitsWithoutGeometry: UnitWithoutGeometry[] = [];

  for (const entry of resolved) {
    if (entry.geometry) {
      units.push({
        id: entry.unit.id,
        unitIdentifier: entry.unit.unitIdentifier,
        unitType: entry.unit.unitType,
        status: entry.unit.status,
        floor: entry.floor,
        geometry: entry.geometry,
      });
    } else {
      unitsWithoutGeometry.push({
        id: entry.unit.id,
        unitIdentifier: entry.unit.unitIdentifier,
        floor: entry.floor,
      });
    }
  }

  return { building, floors, units, unitsWithoutGeometry };
}

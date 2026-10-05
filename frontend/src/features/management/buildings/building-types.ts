/**
 * Wire types for `/api/v1/buildings`.
 *
 * Buildings are always scoped to a parent parcel:
 *   - collection:  GET/POST /api/v1/parcels/{parcel_id}/buildings
 *   - item:        GET/PUT/DELETE /api/v1/buildings/{building_id}
 *
 * Lists return a bare array (not a paginated envelope), mirroring
 * `backend/app/api/v1/buildings.py`.
 */

export interface Building {
  id: string;
  parcel_id: string;
  building_identifier: string;
  name: string | null;
  /** residential | commercial | mixed_use | industrial | institutional */
  building_type: string;
  /** planned | under_construction | completed | demolished */
  construction_status: string;
  footprint_geometry: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** Payload for `POST /api/v1/parcels/{parcel_id}/buildings` (BuildingCreate). */
export interface BuildingCreatePayload {
  building_identifier: string;
  name: string | null;
  building_type: string;
  construction_status: string;
  /** `null` is sent for "no footprint" so the column is cleared explicitly. */
  footprint_geometry: Record<string, unknown> | null;
}

/** All fields optional; the service assigns whatever is present. */
export type BuildingUpdatePayload = Partial<BuildingCreatePayload>;

export const BUILDING_TYPES = [
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'mixed_use', label: 'Mixed use' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'institutional', label: 'Institutional' },
] as const;

export const BUILDING_CONSTRUCTION_STATUSES = [
  { value: 'planned', label: 'Planned' },
  { value: 'under_construction', label: 'Under construction' },
  { value: 'completed', label: 'Completed' },
  { value: 'demolished', label: 'Demolished' },
] as const;

export const BUILDING_TYPE_VALUES = BUILDING_TYPES.map((option) => option.value) as unknown as string[];
export const BUILDING_CONSTRUCTION_STATUS_VALUES =
  BUILDING_CONSTRUCTION_STATUSES.map((option) => option.value) as unknown as string[];

export type BuildingFieldErrors = Record<string, string | undefined>;

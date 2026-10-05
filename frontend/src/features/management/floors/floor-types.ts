/**
 * Wire types for `/api/v1/floors`.
 *
 * Floors are always scoped to a parent building:
 *   - collection: GET/POST /api/v1/buildings/{building_id}/floors
 *   - item:       GET/PUT/DELETE /api/v1/floors/{floor_id}
 *
 * Lists return a bare array. The response carries no unit count, so any count
 * shown in the UI has to be derived from the units list.
 */

export interface Floor {
  id: string;
  building_id: string;
  floor_number: number;
  level_name: string | null;
  /** basement | ground | typical | penthouse | rooftop */
  floor_type: string;
  elevation_min: number;
  elevation_max: number;
  created_at: string;
  updated_at: string;
}

/** Payload for `POST /api/v1/buildings/{building_id}/floors` (FloorCreate). */
export interface FloorCreatePayload {
  floor_number: number;
  level_name: string | null;
  floor_type: string;
  elevation_min: number;
  elevation_max: number;
}

/** All fields optional; the service assigns whatever is present. */
export type FloorUpdatePayload = Partial<FloorCreatePayload>;

export const FLOOR_TYPES = [
  { value: 'basement', label: 'Basement' },
  { value: 'ground', label: 'Ground' },
  { value: 'typical', label: 'Typical' },
  { value: 'penthouse', label: 'Penthouse' },
  { value: 'rooftop', label: 'Rooftop' },
] as const;

export const FLOOR_TYPE_VALUES = FLOOR_TYPES.map((option) => option.value) as unknown as string[];

export type FloorFieldErrors = Record<string, string | undefined>;

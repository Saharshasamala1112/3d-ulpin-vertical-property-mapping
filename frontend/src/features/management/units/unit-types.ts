/**
 * Wire types for `/api/v1/units`.
 *
 * Units are always scoped to a parent floor:
 *   - collection: GET/POST /api/v1/floors/{floor_id}/units
 *   - item:       GET/PUT/DELETE /api/v1/units/{unit_id}
 *   - VDC:        GET/POST /api/v1/units/{unit_id}/vdc
 *
 * Lists return a bare array. There is no building-wide unit endpoint: a
 * building-wide view has to load each floor's units and concatenate.
 */

import type { VdcStatus } from '../vdc/vdc-types';

export interface Unit {
  id: string;
  floor_id: string;
  unit_identifier: string;
  /** residential | commercial | parking | storage | common_area */
  unit_type: string;
  area_sqm: number;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  z_min: number;
  z_max: number;
  /** planned | active | sold | leased | archived */
  status: string;
  vdc_code: string | null;
  /**
   * Server-computed state of `vdc_code`: present | missing | stale | invalid.
   * The backend derives it on every read, so it is never client-side.
   */
  vdc_status: VdcStatus;
  created_at: string;
  updated_at: string;
}

/** Payload for `POST /api/v1/floors/{floor_id}/units` (UnitCreate). */
export interface UnitCreatePayload {
  unit_identifier: string;
  unit_type: string;
  area_sqm: number;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  z_min: number;
  z_max: number;
  status: string;
  vdc_code: string | null;
}

/** All fields optional; the service assigns whatever is present. */
export type UnitUpdatePayload = Partial<UnitCreatePayload>;

/**
 * Response of `GET`/`POST /api/v1/units/{unit_id}/vdc` (`UnitVDCResponse`).
 *
 * Re-exported from the VDC feature so there is a single definition of the
 * shape; the segments are null when `vdc_code` is null or unparseable.
 */
export type { UnitVdc } from '../vdc/vdc-types';

import { apiClient } from '../../../services/api-client';
import type { Unit, UnitCreatePayload, UnitUpdatePayload } from './unit-types';

const BASE = '/api/v1';

const encode = (value: string) => encodeURIComponent(value);

export async function listUnits(floorId: string): Promise<Unit[]> {
  return apiClient.get<Unit[]>(`${BASE}/floors/${encode(floorId)}/units`);
}

export async function getUnit(unitId: string): Promise<Unit> {
  return apiClient.get<Unit>(`${BASE}/units/${encode(unitId)}`);
}

export async function createUnit(floorId: string, payload: UnitCreatePayload): Promise<Unit> {
  return apiClient.post<Unit>(`${BASE}/floors/${encode(floorId)}/units`, payload);
}

export async function updateUnit(unitId: string, payload: UnitUpdatePayload): Promise<Unit> {
  return apiClient.put<Unit>(`${BASE}/units/${encode(unitId)}`, payload);
}

/**
 * ARCHIVE, not delete. Returns 204 with no body.
 *
 * The service sets `status = 'archived'` and keeps the row
 * (`backend/app/services/unit.py`), so the unit still appears in
 * `listUnits` output. Callers must not describe this as removal.
 */
export async function archiveUnit(unitId: string): Promise<void> {
  await apiClient.delete<void>(`${BASE}/units/${encode(unitId)}`);
}

/**
 * Unit-scoped VDC calls, re-exported from the VDC feature so there is a single
 * implementation and existing unit imports keep working.
 *
 * `getUnitVdc` is read-only and answers 200 even when the unit has no code
 * (`status: 'missing'`); only an unknown `unit_id` produces a 404. Note this
 * differs from the parcel ULPIN endpoint, which does 404 on a missing record.
 * `generateUnitVdc` derives the code from the unit hierarchy, persists it, and
 * is idempotent server-side; 422 means the hierarchy cannot be encoded.
 */
export { generateUnitVdc, getUnitVdc } from '../vdc/vdc-service';

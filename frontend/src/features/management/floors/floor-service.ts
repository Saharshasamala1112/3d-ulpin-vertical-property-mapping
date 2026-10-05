import { apiClient } from '../../../services/api-client';
import type { Floor, FloorCreatePayload, FloorUpdatePayload } from './floor-types';

const BASE = '/api/v1';

const encode = (value: string) => encodeURIComponent(value);

export async function listFloors(buildingId: string): Promise<Floor[]> {
  return apiClient.get<Floor[]>(`${BASE}/buildings/${encode(buildingId)}/floors`);
}

export async function getFloor(floorId: string): Promise<Floor> {
  return apiClient.get<Floor>(`${BASE}/floors/${encode(floorId)}`);
}

export async function createFloor(
  buildingId: string,
  payload: FloorCreatePayload
): Promise<Floor> {
  return apiClient.post<Floor>(`${BASE}/buildings/${encode(buildingId)}/floors`, payload);
}

export async function updateFloor(floorId: string, payload: FloorUpdatePayload): Promise<Floor> {
  return apiClient.put<Floor>(`${BASE}/floors/${encode(floorId)}`, payload);
}

/**
 * HARD delete. Returns 204 with no body.
 *
 * The floor row and all units on it are removed in one transaction
 * (`backend/app/services/floor.py`). There is no server-side guard against
 * deleting a floor that still holds units and no preview endpoint, so the UI
 * states the consequence in prose instead of quoting a count.
 */
export async function deleteFloor(floorId: string): Promise<void> {
  await apiClient.delete<void>(`${BASE}/floors/${encode(floorId)}`);
}

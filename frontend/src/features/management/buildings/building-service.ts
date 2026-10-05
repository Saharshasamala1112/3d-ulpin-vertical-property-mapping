import { apiClient } from '../../../services/api-client';
import type { Building, BuildingCreatePayload, BuildingUpdatePayload } from './building-types';

const BASE = '/api/v1';

const encode = (value: string) => encodeURIComponent(value);

export async function listBuildings(parcelId: string): Promise<Building[]> {
  return apiClient.get<Building[]>(`${BASE}/parcels/${encode(parcelId)}/buildings`);
}

export async function getBuilding(buildingId: string): Promise<Building> {
  return apiClient.get<Building>(`${BASE}/buildings/${encode(buildingId)}`);
}

export async function createBuilding(
  parcelId: string,
  payload: BuildingCreatePayload
): Promise<Building> {
  return apiClient.post<Building>(`${BASE}/parcels/${encode(parcelId)}/buildings`, payload);
}

export async function updateBuilding(
  buildingId: string,
  payload: BuildingUpdatePayload
): Promise<Building> {
  return apiClient.put<Building>(`${BASE}/buildings/${encode(buildingId)}`, payload);
}

/**
 * HARD delete. Returns 204 with no body.
 *
 * Unlike parcels and units, this genuinely removes the record: the service
 * deletes the building's floors and those floors' units in the same
 * transaction (see `backend/app/services/building.py`). The confirmation
 * dialog must state that explicitly, and the row disappears from the list.
 *
 * There is no server-side guard against deleting a building that still has
 * children, and no preview endpoint, so the impact has to be described in
 * prose rather than counted.
 */
export async function deleteBuilding(buildingId: string): Promise<void> {
  await apiClient.delete<void>(`${BASE}/buildings/${encode(buildingId)}`);
}

import { apiClient } from '../../../services/api-client';
import type {
  GeoJSONFeature,
  ParcelCreatePayload,
  ParcelListParams,
  ParcelListResponse,
  ParcelUpdatePayload,
} from './parcel-types';
import type { GeoJSONImportCollection, GeoJSONImportReport } from '../shared/geojson-import';

const BASE = '/api/v1/parcels';

/**
 * Build the query string for `GET /api/v1/parcels`.
 *
 * The status filter is exposed as `status` on the wire (the handler declares
 * `alias="status"`), and `per_page` is capped at 100 because the API enforces
 * `Query(ge=1, le=100)` and would reject anything larger with a 422.
 */
function buildListQuery({ page, perPage, status }: ParcelListParams): string {
  const params = new URLSearchParams();
  if (page !== undefined) params.set('page', String(page));
  if (perPage !== undefined) params.set('per_page', String(Math.min(Math.max(perPage, 1), 100)));
  if (status) params.set('status', status);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export async function listParcels(params: ParcelListParams = {}): Promise<ParcelListResponse> {
  return apiClient.get<ParcelListResponse>(`${BASE}${buildListQuery(params)}`);
}

export async function getParcel(parcelId: string): Promise<GeoJSONFeature> {
  return apiClient.get<GeoJSONFeature>(`${BASE}/${encodeURIComponent(parcelId)}`);
}

export async function createParcel(payload: ParcelCreatePayload): Promise<GeoJSONFeature> {
  return apiClient.post<GeoJSONFeature>(BASE, payload);
}

export async function updateParcel(
  parcelId: string,
  payload: ParcelUpdatePayload
): Promise<GeoJSONFeature> {
  return apiClient.put<GeoJSONFeature>(`${BASE}/${encodeURIComponent(parcelId)}`, payload);
}

/**
 * Archive a parcel. Returns 204 with no body.
 *
 * NOTE ON SEMANTICS: despite being a `DELETE`, this does NOT remove the row.
 * `backend/app/api/v1/parcels.py::delete` calls the service, which flips
 * `status` to `archived` and keeps the record. The UI must say "archive", not
 * "delete", and the row stays in the list.
 *
 * It also does not cascade: buildings referencing the parcel are untouched.
 */
export async function archiveParcel(parcelId: string): Promise<void> {
  await apiClient.delete<void>(`${BASE}/${encodeURIComponent(parcelId)}`);
}

export async function importParcelsGeoJSON(
  collection: GeoJSONImportCollection,
  options: { dryRun: boolean; ulpinProperty: string }
): Promise<GeoJSONImportReport> {
  const params = new URLSearchParams({
    dry_run: String(options.dryRun),
    ulpin_property: options.ulpinProperty,
  });
  return apiClient.post<GeoJSONImportReport>(`${BASE}/import?${params}`, collection);
}

export async function importBuildingsGeoJSON(
  collection: GeoJSONImportCollection,
  options: { dryRun: boolean; parcelId: string }
): Promise<GeoJSONImportReport> {
  const params = new URLSearchParams({ dry_run: String(options.dryRun) });
  if (options.parcelId.trim()) params.set('parcel_id', options.parcelId.trim());
  return apiClient.post<GeoJSONImportReport>(`/api/v1/buildings/import?${params}`, collection);
}

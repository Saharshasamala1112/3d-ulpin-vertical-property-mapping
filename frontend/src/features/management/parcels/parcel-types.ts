/**
 * Wire types for `/api/v1/parcels`.
 *
 * Parcels are the only management resource that returns GeoJSON and the only
 * one that is paginated, so the list response is a Feature-collection-ish
 * envelope rather than a bare array. Mirrors `backend/app/schemas/parcel.py`.
 */

export interface GeoJSONGeometry {
  type: string;
  coordinates: unknown;
}

export interface ParcelProperties {
  id: string;
  parcel_identifier: string;
  ulpin: string;
  area_sqm: number;
  /** draft | registered | active | archived */
  status: string;
  metadata: Record<string, unknown> | null;
}

export interface GeoJSONFeature {
  type: 'Feature';
  id: string;
  geometry: GeoJSONGeometry;
  properties: ParcelProperties;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface ParcelListResponse {
  data: GeoJSONFeature[];
  meta: PaginationMeta;
}

export const PARCEL_STATUSES = [
  { value: 'draft', label: 'Draft' },
  { value: 'registered', label: 'Registered' },
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
] as const;

export const PARCEL_STATUS_VALUES = PARCEL_STATUSES.map((option) => option.value) as unknown as string[];

/** Payload for `POST /api/v1/parcels` (ParcelCreate). */
export interface ParcelCreatePayload {
  parcel_identifier: string;
  ulpin: string;
  geometry: Record<string, unknown>;
  area_sqm: number;
  status: string;
  metadata: Record<string, unknown> | null;
}

/**
 * Payload for `PUT /api/v1/parcels/{id}` (ParcelUpdate).
 *
 * Every field is optional, and the service applies partial updates, so the
 * edit dialog only sends the fields the user actually changed.
 */
export type ParcelUpdatePayload = Partial<ParcelCreatePayload>;

export interface ParcelListParams {
  page?: number;
  perPage?: number;
  status?: string | null;
}

export type ParcelFieldErrors = Record<string, string | undefined>;

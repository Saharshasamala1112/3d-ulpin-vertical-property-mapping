import { apiClient } from '../../../services/api-client';
import type {
  UnitVdc,
  VdcGenerateResult,
  VdcParsed,
  VdcValidateResult,
} from './vdc-types';

/**
 * Typed access to the Feature 33 VDC endpoints.
 *
 * Every call goes through the shared `apiClient` so the auth header, the
 * single refresh-on-401 path, and the `ApiError` normalization in
 * `services/api-error.ts` keep working unchanged.
 *
 * Nothing here parses or validates a VDC locally: the backend owns the segment
 * grammar and the checksum algorithm, and the frontend must never re-implement
 * them.
 */

const BASE = '/api/v1';

const encode = (value: string) => encodeURIComponent(value);

/**
 * Read a unit's stored VDC code and its parsed segments. Read-only.
 *
 * Answers 200 even when the unit has no code (`status: 'missing'`); only an
 * unknown `unit_id` produces a 404.
 */
export async function getUnitVdc(unitId: string): Promise<UnitVdc> {
  return apiClient.get<UnitVdc>(`${BASE}/units/${encode(unitId)}/vdc`);
}

/**
 * Derive the VDC from the unit's parcel/building/floor/identifier hierarchy,
 * persist it, and return the stored code with its segments.
 *
 * Idempotent server-side, so a repeat call is safe; the UI still guards against
 * firing concurrent requests. 422 means the hierarchy cannot be encoded.
 */
export async function generateUnitVdc(unitId: string): Promise<UnitVdc> {
  return apiClient.post<UnitVdc>(`${BASE}/units/${encode(unitId)}/vdc`);
}

/**
 * Validate a VDC string's grammar and checksum.
 *
 * Resolves with `valid: false` for a malformed VDC — that is a normal result,
 * not a failure. Rejects only on transport or request-shape problems.
 */
export async function validateVdc(vdc: string): Promise<VdcValidateResult> {
  return apiClient.post<VdcValidateResult>(`${BASE}/vdc/validate`, { vdc });
}

/**
 * Decompose a VDC into its five canonical segments.
 *
 * Rejects with a 422 `ApiError` whose `details.vdc_errors` carries the same
 * structured errors `validateVdc` would return; use `extractVdcErrors` to
 * read them back.
 */
export async function parseVdc(vdc: string): Promise<VdcParsed> {
  return apiClient.post<VdcParsed>(`${BASE}/vdc/parse`, { vdc });
}

/** Combine four components into a canonical VDC. */
export async function generateVdc(components: {
  ulpin: string;
  domain: string;
  level: string;
  unit: string;
}): Promise<VdcGenerateResult> {
  return apiClient.post<VdcGenerateResult>(`${BASE}/vdc/generate`, components);
}

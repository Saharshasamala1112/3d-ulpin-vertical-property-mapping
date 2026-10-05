/**
 * Wire types for the Feature 33 VDC API.
 *
 * These mirror the backend contracts exactly; the backend is the source of
 * truth and must not be re-implemented in TypeScript:
 *   - `VdcStatus`             <- `VDCStatus` in backend/app/schemas/unit.py
 *   - `UnitVdc`               <- `UnitVDCResponse` in the same module
 *   - `VdcParsed`             <- `VDCParsed` in backend/app/schemas/vdc.py
 *   - `VdcValidationError`    <- `VDCErrorDetail` in the same module
 *   - `VdcValidateResult`     <- `VDCValidateResponse` in the same module
 *   - `VdcGenerateResult`     <- `VDCGenerateResponse` in the same module
 */

/**
 * Lifecycle of a unit's stored VDC code, decided server-side by `_vdc_status`.
 *
 * The four values are closed: the backend never emits anything else, and the UI
 * must not invent alternatives.
 */
export type VdcStatus = 'present' | 'missing' | 'stale' | 'invalid';

/** Response of `GET /api/v1/units/{unit_id}/vdc` and `POST /api/v1/units/{unit_id}/vdc`. */
export interface UnitVdc {
  unit_id: string;
  vdc_code: string | null;
  status: VdcStatus;
  /** Parsed segments; null whenever `vdc_code` is null or unparseable. */
  ulpin: string | null;
  domain: string | null;
  level: string | null;
  unit: string | null;
  checksum: string | null;
}

/**
 * Response of `POST /api/v1/vdc/parse`: exactly the five canonical segments.
 *
 * The backend returns no separate "canonical" field, so the canonical VDC form
 * is reconstructed by re-joining these segments with `-` (see
 * `canonicalVdc`), which is exactly how `parse_vdc` split the input.
 */
export interface VdcParsed {
  ulpin: string;
  domain: string;
  level: string;
  unit: string;
  checksum: string;
}

/** One structured validation error, tied to a specific segment. */
export interface VdcValidationError {
  segment: string;
  code: string;
  message: string;
}

/**
 * Response of `POST /api/v1/vdc/validate`.
 *
 * An invalid VDC is an *expected* answer, so this endpoint answers HTTP 200 with
 * `valid: false`. A non-2xx response therefore means a transport or request-body
 * problem, never "this VDC is malformed".
 */
export interface VdcValidateResult {
  valid: boolean;
  errors: VdcValidationError[];
}

/** Response of `POST /api/v1/vdc/generate`. */
export interface VdcGenerateResult {
  vdc: string;
}

/** The five segments in specification order, used for display. */
export const VDC_SEGMENT_NAMES = ['ulpin', 'domain', 'level', 'unit', 'checksum'] as const;

export type VdcSegmentName = (typeof VDC_SEGMENT_NAMES)[number];

/**
 * Rebuild the canonical VDC string from parsed segments.
 *
 * The specification defines the canonical form as the five segments joined by
 * `-` (ULPIN-DOMAIN-LEVEL-UNIT-CHECKSUM, e.g. `GEOSX00001-A-G-1-ZY`), and
 * `parse_vdc` performs exactly that split after stripping outer whitespace, so
 * re-joining is lossless rather than a guess.
 */
export function canonicalVdc(parsed: VdcParsed): string {
  return VDC_SEGMENT_NAMES.map((segment) => parsed[segment]).join('-');
}

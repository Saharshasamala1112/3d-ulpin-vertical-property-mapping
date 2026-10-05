import type { ApiError } from '../../../services/api-error';
import type { VdcValidationError } from './vdc-types';

/**
 * The single translation table for backend VDC validator codes.
 *
 * Every code the backend can emit is listed here, and it is the *only* place in
 * the frontend that knows about them. Components must call
 * `describeVdcError` rather than comparing code strings themselves.
 *
 * The list is exhaustive by construction: `vdc_parser.py` emits
 * `lowercase_character`, `invalid_character`, `invalid_<segment>` for each of
 * the five segments, `invalid_segment_count` and `empty_segment`; and
 * `vdc_validation.py` adds `checksum_mismatch`.
 */
const VALIDATOR_CODE_LABELS: Record<string, string> = {
  lowercase_character: 'Lowercase character',
  invalid_character: 'Invalid character',
  invalid_ulpin: 'Invalid ULPIN',
  invalid_domain: 'Invalid domain',
  invalid_level: 'Invalid level',
  invalid_unit: 'Invalid unit number',
  invalid_checksum: 'Invalid checksum',
  invalid_segment_count: 'Wrong number of segments',
  empty_segment: 'Empty segment',
  checksum_mismatch: 'Checksum mismatch',
};

/** Pseudo-segment the backend uses for whole-code structural problems. */
const STRUCTURE_SEGMENT = 'structure';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Coerce one untrusted entry into a `VdcValidationError`, or null if unusable. */
function toValidationError(value: unknown): VdcValidationError | null {
  if (!isRecord(value)) return null;
  const { segment, code, message } = value;
  if (typeof segment !== 'string' || typeof code !== 'string' || typeof message !== 'string') {
    return null;
  }
  return { segment, code, message };
}

/**
 * Pull the structured per-segment errors out of a failed request.
 *
 * `POST /api/v1/vdc/parse` answers 422 with the Feature 12 envelope
 * `{"error": {"code": "VALIDATION_ERROR", "details": {"vdc_errors": [...]}}}`,
 * which `api-error.ts` normalizes onto `ApiError.details.vdc_errors`.
 *
 * Returns an empty array when the payload carries no structured errors — the
 * caller should then fall back to the error banner, since there is nothing
 * segment-level to render.
 */
export function extractVdcErrors(error: ApiError): VdcValidationError[] {
  const raw = error.details?.vdc_errors;
  if (!Array.isArray(raw)) return [];
  return raw
    .map(toValidationError)
    .filter((entry): entry is VdcValidationError => entry !== null);
}

/**
 * A structured error, ready to render: the raw code, a human-readable label, and
 * which segment it refers to.
 */
export interface DescribedVdcError {
  segment: string;
  code: string;
  label: string;
  message: string;
  /** True when `code` was not in the translation table. */
  unknown: boolean;
  /** True for the backend's whole-code `structure` pseudo-segment. */
  structural: boolean;
}

/**
 * Map one validator error onto display text.
 *
 * Unknown codes are never discarded: they fall back to a label that still shows
 * the raw code, so a backend addition is visible rather than silently hidden.
 */
export function describeVdcError(error: VdcValidationError): DescribedVdcError {
  const label = VALIDATOR_CODE_LABELS[error.code];
  return {
    segment: error.segment,
    code: error.code,
    label: label ?? `Unrecognised check (${error.code})`,
    message: error.message,
    unknown: label === undefined,
    structural: error.segment === STRUCTURE_SEGMENT,
  };
}

/** Display name for a segment: `ULPIN`, `DOMAIN`, ... and `Code structure`. */
export function describeSegment(segment: string): string {
  if (segment === STRUCTURE_SEGMENT) return 'Code structure';
  return segment.toUpperCase();
}

/** Short human summary of a status, used in the badge `title`. */
export const VDC_STATUS_LABELS: Record<string, string> = {
  present: 'Valid and matches the unit hierarchy',
  missing: 'No VDC code has been assigned',
  stale: 'Valid code that no longer matches the unit hierarchy',
  invalid: 'Stored code fails VDC validation',
};

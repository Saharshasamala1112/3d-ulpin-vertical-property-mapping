import { parseGeoJsonText } from '../shared/geojson';
import {
  PARCEL_STATUS_VALUES,
  type ParcelCreatePayload,
  type ParcelFieldErrors,
  type ParcelUpdatePayload,
} from './parcel-types';
import { isJsonEqual } from '../shared/json-diff';

export interface ParcelFormValues {
  parcel_identifier: string;
  ulpin: string;
  area_sqm: string;
  status: string;
  geometryText: string;
  metadataText: string;
}

export const emptyParcelForm: ParcelFormValues = {
  parcel_identifier: '',
  ulpin: '',
  area_sqm: '',
  status: 'draft',
  geometryText: '',
  metadataText: '',
};

type ValidationOutcome =
  | { ok: true; create: ParcelCreatePayload }
  | { ok: false; errors: ParcelFieldErrors };

/**
 * Validate the parcel form and build the create payload.
 *
 * GeoJSON is parsed here rather than on the server because the API only checks
 * that `geometry` is a dict and malformed content becomes an opaque 500. See
 * `shared/geojson.ts`.
 */
export function validateParcelForm(values: ParcelFormValues): ValidationOutcome {
  const errors: ParcelFieldErrors = {};

  const identifier = values.parcel_identifier.trim();
  if (!identifier) {
    errors.parcel_identifier = 'Parcel identifier is required.';
  } else if (identifier.length > 255) {
    errors.parcel_identifier = 'Parcel identifier must be at most 255 characters.';
  }

  const ulpin = values.ulpin.trim();
  if (!ulpin) {
    errors.ulpin = 'ULPIN is required.';
  } else if (ulpin.length > 255) {
    errors.ulpin = 'ULPIN must be at most 255 characters.';
  }

  const areaRaw = values.area_sqm.trim();
  const area = Number(areaRaw);
  if (areaRaw === '') {
    errors.area_sqm = 'Area is required.';
  } else if (!Number.isFinite(area)) {
    errors.area_sqm = 'Area must be a number.';
  } else if (area <= 0) {
    // Matches `Field(gt=0)` on ParcelCreate.area_sqm.
    errors.area_sqm = 'Area must be greater than 0.';
  }

  if (!PARCEL_STATUS_VALUES.includes(values.status)) {
    errors.status = 'Select a valid status.';
  }

  const geometry = parseGeoJsonText(values.geometryText);
  if (!geometry.ok) {
    errors.geometryText = geometry.error;
  }

  let metadata: Record<string, unknown> | null = null;
  const metadataRaw = values.metadataText.trim();
  if (metadataRaw !== '') {
    let parsed: unknown;
    try {
      parsed = JSON.parse(metadataRaw);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      errors.metadataText = `Invalid JSON: ${detail}`;
    }
    if (errors.metadataText === undefined) {
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        errors.metadataText = 'Metadata must be a JSON object.';
      } else {
        metadata = parsed as Record<string, unknown>;
      }
    }
  }

  if (Object.keys(errors).length > 0 || !geometry.ok) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    create: {
      parcel_identifier: identifier,
      ulpin,
      geometry: geometry.value,
      area_sqm: area,
      status: values.status,
      metadata,
    },
  };
}

/**
 * Build the `PUT` payload, sending only fields that differ from `original`.
 *
 * `ParcelUpdate` fields are all optional and the service assigns whatever is
 * present, so sending the full object would clobber concurrent edits to fields
 * the user never touched.
 */
export function buildParcelUpdate(
  original: ParcelCreatePayload,
  values: ParcelFormValues
): { ok: true; update: ParcelUpdatePayload } | { ok: false; errors: ParcelFieldErrors } {
  const validated = validateParcelForm(values);
  if (!validated.ok) {
    return validated;
  }

  const next = validated.create;
  const update: ParcelUpdatePayload = {};

  if (next.parcel_identifier !== original.parcel_identifier) {
    update.parcel_identifier = next.parcel_identifier;
  }
  if (next.ulpin !== original.ulpin) {
    update.ulpin = next.ulpin;
  }
  if (next.area_sqm !== original.area_sqm) {
    update.area_sqm = next.area_sqm;
  }
  if (next.status !== original.status) {
    update.status = next.status;
  }
  if (!isJsonEqual(next.geometry, original.geometry)) {
    update.geometry = next.geometry;
  }
  if (!isJsonEqual(next.metadata ?? null, original.metadata ?? null)) {
    update.metadata = next.metadata;
  }

  return { ok: true, update };
}

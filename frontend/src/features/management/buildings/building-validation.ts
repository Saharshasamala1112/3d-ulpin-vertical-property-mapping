import { parseGeoJsonText } from '../shared/geojson';
import {
  BUILDING_CONSTRUCTION_STATUS_VALUES,
  BUILDING_TYPE_VALUES,
  type BuildingCreatePayload,
  type BuildingFieldErrors,
  type BuildingUpdatePayload,
} from './building-types';
import { isJsonEqual } from '../shared/json-diff';

export interface BuildingFormValues {
  building_identifier: string;
  name: string;
  building_type: string;
  construction_status: string;
  footprintText: string;
}

export const emptyBuildingForm: BuildingFormValues = {
  building_identifier: '',
  name: '',
  building_type: 'residential',
  construction_status: 'planned',
  footprintText: '',
};

type Outcome =
  | { ok: true; create: BuildingCreatePayload }
  | { ok: false; errors: BuildingFieldErrors };

/**
 * Validate the building form and build the create payload.
 *
 * `building_type` is required by the API (no default), so an empty selection
 * is rejected here rather than relying on a 422 round trip.
 */
export function validateBuildingForm(values: BuildingFormValues): Outcome {
  const errors: BuildingFieldErrors = {};

  const identifier = values.building_identifier.trim();
  if (!identifier) {
    errors.building_identifier = 'Building identifier is required.';
  } else if (identifier.length > 255) {
    errors.building_identifier = 'Building identifier must be at most 255 characters.';
  }

  const name = values.name.trim();
  // The API declares `name: str | None = Field(min_length=1, ...)`, so an
  // empty string is NOT an acceptable substitute for null.
  if (name.length > 255) {
    errors.name = 'Name must be at most 255 characters.';
  }

  if (!BUILDING_TYPE_VALUES.includes(values.building_type)) {
    errors.building_type = 'Select a valid building type.';
  }

  if (!BUILDING_CONSTRUCTION_STATUS_VALUES.includes(values.construction_status)) {
    errors.construction_status = 'Select a valid construction status.';
  }

  let footprint: Record<string, unknown> | null = null;
  const footprintRaw = values.footprintText.trim();
  if (footprintRaw !== '') {
    const parsed = parseGeoJsonText(footprintRaw);
    if (parsed.ok) {
      footprint = parsed.value;
    } else {
      errors.footprintText = parsed.error;
    }
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    create: {
      building_identifier: identifier,
      name: name === '' ? null : name,
      building_type: values.building_type,
      construction_status: values.construction_status,
      footprint_geometry: footprint,
    },
  };
}

/** Build the `PUT` payload, sending only fields that differ from `original`. */
export function buildBuildingUpdate(
  original: BuildingCreatePayload,
  values: BuildingFormValues
): { ok: true; update: BuildingUpdatePayload } | { ok: false; errors: BuildingFieldErrors } {
  const validated = validateBuildingForm(values);
  if (!validated.ok) return validated;

  const next = validated.create;
  const update: BuildingUpdatePayload = {};

  if (next.building_identifier !== original.building_identifier) {
    update.building_identifier = next.building_identifier;
  }
  if (next.name !== original.name) {
    update.name = next.name;
  }
  if (next.building_type !== original.building_type) {
    update.building_type = next.building_type;
  }
  if (next.construction_status !== original.construction_status) {
    update.construction_status = next.construction_status;
  }
  if (!isJsonEqual(next.footprint_geometry, original.footprint_geometry)) {
    update.footprint_geometry = next.footprint_geometry;
  }

  return { ok: true, update };
}

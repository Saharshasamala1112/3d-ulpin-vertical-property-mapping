import { FLOOR_TYPE_VALUES, type FloorCreatePayload, type FloorFieldErrors, type FloorUpdatePayload } from './floor-types';

export interface FloorFormValues {
  floor_number: string;
  level_name: string;
  floor_type: string;
  elevation_min: string;
  elevation_max: string;
}

export const emptyFloorForm: FloorFormValues = {
  floor_number: '',
  level_name: '',
  floor_type: 'typical',
  elevation_min: '',
  elevation_max: '',
};

type Outcome =
  | { ok: true; create: FloorCreatePayload }
  | { ok: false; errors: FloorFieldErrors };

/** Parse a required finite number from a text field. */
function parseNumberField(
  raw: string,
  field: string,
  label: string,
  errors: FloorFieldErrors
): number {
  const trimmed = raw.trim();
  if (trimmed === '') {
    errors[field] = `${label} is required.`;
    return 0;
  }
  const value = Number(trimmed);
  if (!Number.isFinite(value)) {
    errors[field] = `${label} must be a number.`;
    return 0;
  }
  return value;
}

/**
 * Validate the floor form and build the create payload.
 *
 * NOTE: `FloorCreate`/`FloorUpdate` in `backend/app/schemas/floor.py` have no
 * model validator, so the API does NOT enforce that
 * `elevation_min <= elevation_max` (unlike `UnitCreate`, which does). This
 * form therefore validates only presence and numeric type, and deliberately
 * does not invent an ordering rule the API would not enforce. The page
 * surfaces this gap in its copy instead.
 */
export function validateFloorForm(values: FloorFormValues): Outcome {
  const errors: FloorFieldErrors = {};

  const floorNumberRaw = values.floor_number.trim();
  if (floorNumberRaw === '') {
    errors.floor_number = 'Floor number is required.';
  } else if (!/^-?\d+$/.test(floorNumberRaw)) {
    errors.floor_number = 'Floor number must be a whole number (basements may be negative).';
  }

  const levelName = values.level_name.trim();
  if (levelName.length > 255) {
    errors.level_name = 'Level name must be at most 255 characters.';
  }

  if (!FLOOR_TYPE_VALUES.includes(values.floor_type)) {
    errors.floor_type = 'Select a valid floor type.';
  }

  const elevationMin = parseNumberField(values.elevation_min, 'elevation_min', 'Minimum elevation', errors);
  const elevationMax = parseNumberField(values.elevation_max, 'elevation_max', 'Maximum elevation', errors);

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    create: {
      floor_number: Number(floorNumberRaw),
      // `level_name` is `str | None` with min_length=1, so blank must be null.
      level_name: levelName === '' ? null : levelName,
      floor_type: values.floor_type,
      elevation_min: elevationMin,
      elevation_max: elevationMax,
    },
  };
}

/** Build the `PUT` payload, sending only fields that differ from `original`. */
export function buildFloorUpdate(
  original: FloorCreatePayload,
  values: FloorFormValues
): { ok: true; update: FloorUpdatePayload } | { ok: false; errors: FloorFieldErrors } {
  const validated = validateFloorForm(values);
  if (!validated.ok) return validated;

  const next = validated.create;
  const update: FloorUpdatePayload = {};

  if (next.floor_number !== original.floor_number) update.floor_number = next.floor_number;
  if (next.level_name !== original.level_name) update.level_name = next.level_name;
  if (next.floor_type !== original.floor_type) update.floor_type = next.floor_type;
  if (next.elevation_min !== original.elevation_min) update.elevation_min = next.elevation_min;
  if (next.elevation_max !== original.elevation_max) update.elevation_max = next.elevation_max;

  return { ok: true, update };
}

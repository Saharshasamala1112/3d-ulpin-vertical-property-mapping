/**
 * Unit form validation.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * BOUNDING BOX RULE — read before changing anything here.
 *
 * W34 requires STRICT ordering: `min < max`, and equality is rejected.
 *
 * The API on this base (`origin/epic/core-palatform-2`) is more permissive: it
 * only rejects `min > max` in `backend/app/schemas/unit.py` and in
 * `backend/app/services/unit.py`, so it accepts a zero-volume box where
 * `min == max`. This client is therefore STRICTER than the current server.
 *
 * That is intentional: W34's acceptance criteria demand the strict rule. The
 * only consequence is that this UI refuses to create a degenerate box the API
 * would have accepted.
 *
 * Feature 29 (`origin/feat/unify-unit-geometry-bounds`, commit f37be70) moves
 * the box into `property_geometry` as `Decimal(18, 6)` and already enforces the
 * strict rule server-side. When that branch lands, this module needs no
 * behavioural change: the comparison below already matches it, and the request
 * field names (`x_min` ... `z_max`) are identical in both revisions.
 *
 * To relax or tighten the rule, change ONLY `isStrictlyOrdered` below.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type { UnitCreatePayload, UnitUpdatePayload } from './unit-types';

/** Client-side bounding box rule. Strict today, matching W34 + Feature 29. */
export const isStrictlyOrdered = (min: number, max: number): boolean => min < max;

export const BBOX_RULE_DESCRIPTION = 'Each minimum must be strictly less than its maximum (min < max).';

export const UNIT_TYPES = [
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'parking', label: 'Parking' },
  { value: 'storage', label: 'Storage' },
  { value: 'common_area', label: 'Common area' },
] as const;

export const UNIT_STATUSES = [
  { value: 'planned', label: 'Planned' },
  { value: 'active', label: 'Active' },
  { value: 'sold', label: 'Sold' },
  { value: 'leased', label: 'Leased' },
  { value: 'archived', label: 'Archived' },
] as const;

export const UNIT_TYPE_VALUES = UNIT_TYPES.map((option) => option.value) as unknown as string[];
export const UNIT_STATUS_VALUES = UNIT_STATUSES.map((option) => option.value) as unknown as string[];

export interface BoundingBoxValues {
  x_min: string;
  x_max: string;
  y_min: string;
  y_max: string;
  z_min: string;
  z_max: string;
}

export type FieldErrors = Record<string, string | undefined>;

const AXES = ['x', 'y', 'z'] as const;

type Axis = (typeof AXES)[number];

/**
 * Parse the six bbox inputs.
 *
 * Returns either the numeric box or a field-keyed error map. Empty inputs are
 * reported per field so the form can highlight the exact missing control.
 */
export function parseBoundingBox(
  values: BoundingBoxValues
): { ok: true; value: Record<Axis, { min: number; max: number }> } | { ok: false; errors: FieldErrors } {
  const errors: FieldErrors = {};
  const parsed: Partial<Record<Axis, { min: number; max: number }>> = {};

  for (const axis of AXES) {
    const rawMin = values[`${axis}_min` as keyof BoundingBoxValues];
    const rawMax = values[`${axis}_max` as keyof BoundingBoxValues];
    const minKey = `${axis}_min`;
    const maxKey = `${axis}_max`;

    const minTrimmed = (rawMin ?? '').trim();
    const maxTrimmed = (rawMax ?? '').trim();

    if (minTrimmed === '') errors[minKey] = `${axis.toUpperCase()}_min is required.`;
    if (maxTrimmed === '') errors[maxKey] = `${axis.toUpperCase()}_max is required.`;

    const min = Number(minTrimmed);
    const max = Number(maxTrimmed);

    if (minTrimmed !== '' && !Number.isFinite(min)) {
      errors[minKey] = `${minKey} must be a number.`;
    }
    if (maxTrimmed !== '' && !Number.isFinite(max)) {
      errors[maxKey] = `${maxKey} must be a number.`;
    }

    if (errors[minKey] || errors[maxKey]) continue;

    if (!isStrictlyOrdered(min, max)) {
      // Distinguish equality from inversion: the message is the same rule, but
      // equality is the case most likely to surprise users.
      const reason =
        min === max
          ? `${minKey} and ${maxKey} must differ; equal values give the unit zero extent.`
          : `${minKey} must be strictly less than ${maxKey}.`;
      errors[maxKey] = reason;
      continue;
    }

    parsed[axis] = { min, max };
  }

  if (Object.keys(errors).length > 0 || AXES.some((axis) => !parsed[axis])) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    value: {
      x: parsed.x as { min: number; max: number },
      y: parsed.y as { min: number; max: number },
      z: parsed.z as { min: number; max: number },
    },
  };
}

export interface UnitFormValues {
  unit_identifier: string;
  unit_type: string;
  area_sqm: string;
  status: string;
  vdc_code: string;
  bbox: BoundingBoxValues;
}

export type UnitValidationResult =
  | { ok: true; payload: UnitCreatePayload }
  | { ok: false; errors: FieldErrors };

/** Validate the whole unit form and build the create/update payload. */
export function validateUnitForm(values: UnitFormValues): UnitValidationResult {
  const errors: FieldErrors = {};

  const identifier = values.unit_identifier.trim();
  if (!identifier) {
    errors.unit_identifier = 'Unit identifier is required.';
  } else if (identifier.length > 255) {
    errors.unit_identifier = 'Unit identifier must be at most 255 characters.';
  }

  if (!UNIT_TYPE_VALUES.includes(values.unit_type)) {
    errors.unit_type = 'Select a valid unit type.';
  }

  if (!UNIT_STATUS_VALUES.includes(values.status)) {
    errors.status = 'Select a valid status.';
  }

  const areaRaw = values.area_sqm.trim();
  const area = Number(areaRaw);
  if (areaRaw === '') {
    errors.area_sqm = 'Area is required.';
  } else if (!Number.isFinite(area)) {
    errors.area_sqm = 'Area must be a number.';
  } else if (area <= 0) {
    errors.area_sqm = 'Area must be greater than 0.';
  }

  const bbox = parseBoundingBox(values.bbox);
  if (!bbox.ok) {
    Object.assign(errors, bbox.errors);
  }

  const vdc = values.vdc_code.trim();

  if (Object.keys(errors).length > 0 || !bbox.ok) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    payload: {
      unit_identifier: identifier,
      unit_type: values.unit_type,
      area_sqm: area,
      status: values.status,
      x_min: bbox.value.x.min,
      x_max: bbox.value.x.max,
      y_min: bbox.value.y.min,
      y_max: bbox.value.y.max,
      z_min: bbox.value.z.min,
      z_max: bbox.value.z.max,
      // Send `null` rather than "" so the API applies its default on create.
      vdc_code: vdc === '' ? null : vdc,
    },
  };
}

/**
 * Build the `PUT` payload, sending only fields that differ from `original`.
 *
 * Every field is sent on create, but a `PUT` with the whole payload would
 * needlessly re-trigger the bounding-box validator, so an unchanged form
 * submits an empty object. Note the API's `UnitUpdate` validator skips any
 * axis whose counterpart is absent, so a genuine partial update is also safe.
 */
export function buildUnitUpdate(
  original: UnitCreatePayload,
  values: UnitFormValues
): { ok: true; update: UnitUpdatePayload } | { ok: false; errors: FieldErrors } {
  const validated = validateUnitForm(values);
  if (!validated.ok) return validated;

  const next = validated.payload;
  const update: UnitUpdatePayload = {};

  if (next.unit_identifier !== original.unit_identifier) {
    update.unit_identifier = next.unit_identifier;
  }
  if (next.unit_type !== original.unit_type) update.unit_type = next.unit_type;
  if (next.area_sqm !== original.area_sqm) update.area_sqm = next.area_sqm;
  if (next.x_min !== original.x_min) update.x_min = next.x_min;
  if (next.x_max !== original.x_max) update.x_max = next.x_max;
  if (next.y_min !== original.y_min) update.y_min = next.y_min;
  if (next.y_max !== original.y_max) update.y_max = next.y_max;
  if (next.z_min !== original.z_min) update.z_min = next.z_min;
  if (next.z_max !== original.z_max) update.z_max = next.z_max;
  if (next.status !== original.status) update.status = next.status;
  if (next.vdc_code !== original.vdc_code) update.vdc_code = next.vdc_code;

  return { ok: true, update };
}

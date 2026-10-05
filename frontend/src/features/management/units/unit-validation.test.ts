import { describe, it, expect } from 'vitest';
import {
  buildUnitUpdate,
  isStrictlyOrdered,
  parseBoundingBox,
  validateUnitForm,
  type UnitFormValues,
} from './unit-validation';
import type { UnitCreatePayload } from './unit-types';

const bbox = { x_min: '0', x_max: '5', y_min: '0', y_max: '6', z_min: '0', z_max: '3' };

function form(overrides: Partial<UnitFormValues> = {}): UnitFormValues {
  return {
    unit_identifier: 'U-101',
    unit_type: 'residential',
    area_sqm: '85.5',
    status: 'active',
    vdc_code: '',
    bbox,
    ...overrides,
  };
}

const original: UnitCreatePayload = {
  unit_identifier: 'U-101',
  unit_type: 'residential',
  area_sqm: 85.5,
  x_min: 0,
  x_max: 5,
  y_min: 0,
  y_max: 6,
  z_min: 0,
  z_max: 3,
  status: 'active',
  vdc_code: null,
};

describe('unit-validation', () => {
  describe('isStrictlyOrdered', () => {
    it('rejects equality, unlike the current API', () => {
      expect(isStrictlyOrdered(1, 1)).toBe(false);
    });

    it('accepts min < max', () => {
      expect(isStrictlyOrdered(0, 1)).toBe(true);
    });
  });

  describe('parseBoundingBox', () => {
    it('requires all six values', () => {
      const result = parseBoundingBox({ ...bbox, z_max: '' });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(Object.keys(result.errors).length).toBeGreaterThan(0);
    });

    it('rejects a zero-volume axis with a dedicated message', () => {
      const result = parseBoundingBox({ ...bbox, x_min: '5', x_max: '5' });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.x_max).toMatch(/must differ/i);
    });

    it('rejects an inverted axis', () => {
      const result = parseBoundingBox({ ...bbox, y_min: '9', y_max: '2' });
      expect(result.ok).toBe(false);
    });

    it('rejects non-numeric input', () => {
      const result = parseBoundingBox({ ...bbox, x_min: 'abc' });
      expect(result.ok).toBe(false);
    });

    it('parses valid values to numbers', () => {
      const result = parseBoundingBox(bbox);
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.value.x).toEqual({ min: 0, max: 5 });
    });
  });

  describe('validateUnitForm', () => {
    it('builds a create payload with vdc_code: null when blank', () => {
      const result = validateUnitForm(form());
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.payload.unit_identifier).toBe('U-101');
        expect(result.payload.area_sqm).toBe(85.5);
        expect(result.payload.vdc_code).toBeNull();
        expect(result.payload).not.toHaveProperty('floor_id');
      }
    });

    it('keeps a provided vdc_code', () => {
      const result = validateUnitForm(form({ vdc_code: ' VDC-7 ' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.payload.vdc_code).toBe('VDC-7');
    });

    it('requires an identifier', () => {
      const result = validateUnitForm(form({ unit_identifier: '  ' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.unit_identifier).toMatch(/required/i);
    });

    it('rejects an area of zero, matching the API gt=0 rule', () => {
      const result = validateUnitForm(form({ area_sqm: '0' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.area_sqm).toMatch(/greater than 0/i);
    });

    it('rejects a negative area', () => {
      const result = validateUnitForm(form({ area_sqm: '-5' }));
      expect(result.ok).toBe(false);
    });

    it('rejects an unknown unit type', () => {
      const result = validateUnitForm(form({ unit_type: 'igloo' }));
      expect(result.ok).toBe(false);
    });

    it('rejects an unknown status', () => {
      const result = validateUnitForm(form({ status: 'pending' }));
      expect(result.ok).toBe(false);
    });

    it('is stricter than the API by rejecting a degenerate bounding box', () => {
      const result = validateUnitForm(form({ bbox: { ...bbox, z_min: '3', z_max: '3' } }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.z_max).toMatch(/less than|differ/i);
    });
  });

  describe('buildUnitUpdate', () => {
    it('sends an empty payload when nothing changed', () => {
      const result = buildUnitUpdate(original, form());
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({});
    });

    it('sends only the changed field', () => {
      const result = buildUnitUpdate(original, form({ status: 'sold' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ status: 'sold' });
    });

    it('sends vdc_code: null when it is cleared', () => {
      const result = buildUnitUpdate({ ...original, vdc_code: 'VDC-7' }, form());
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ vdc_code: null });
    });

    it('sends every bounding-box field when one axis moves', () => {
      const result = buildUnitUpdate(original, form({ bbox: { ...bbox, x_max: '8' } }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ x_max: 8 });
    });

    it('returns validation errors rather than a partial update', () => {
      const result = buildUnitUpdate(original, form({ area_sqm: '-1' }));
      expect(result.ok).toBe(false);
    });
  });
});

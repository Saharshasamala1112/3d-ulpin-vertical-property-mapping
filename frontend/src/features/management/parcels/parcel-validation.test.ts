import { describe, it, expect } from 'vitest';
import { buildParcelUpdate, emptyParcelForm, validateParcelForm, type ParcelFormValues } from './parcel-validation';
import type { ParcelCreatePayload } from './parcel-types';

const VALID_GEOMETRY = { type: 'MultiPolygon', coordinates: [[[[0, 0], [1, 0], [1, 1], [0, 0]]]] };

function form(overrides: Partial<ParcelFormValues> = {}): ParcelFormValues {
  return {
    ...emptyParcelForm,
    parcel_identifier: 'SEC-1',
    ulpin: 'ULPIN-1',
    area_sqm: '100',
    status: 'draft',
    geometryText: JSON.stringify(VALID_GEOMETRY),
    ...overrides,
  };
}

describe('validateParcelForm', () => {
  it('accepts a complete form and returns the create payload', () => {
    const result = validateParcelForm(form());

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.create).toEqual({
      parcel_identifier: 'SEC-1',
      ulpin: 'ULPIN-1',
      area_sqm: 100,
      status: 'draft',
      geometry: VALID_GEOMETRY,
      metadata: null,
    });
  });

  it('trims identifier and ULPIN', () => {
    const result = validateParcelForm(form({ parcel_identifier: '  SEC-9  ', ulpin: ' ULPIN-9 ' }));

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.create.parcel_identifier).toBe('SEC-9');
    expect(result.create.ulpin).toBe('ULPIN-9');
  });

  it('requires an identifier and a ULPIN', () => {
    const result = validateParcelForm(form({ parcel_identifier: '  ', ulpin: '' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.parcel_identifier).toBeTruthy();
    expect(result.errors.ulpin).toBeTruthy();
  });

  it('rejects an area of 0, matching Field(gt=0) on ParcelCreate', () => {
    const result = validateParcelForm(form({ area_sqm: '0' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.area_sqm).toBe('Area must be greater than 0.');
  });

  it('rejects a negative area', () => {
    const result = validateParcelForm(form({ area_sqm: '-5' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.area_sqm).toBeTruthy();
  });

  it('rejects a non-numeric area', () => {
    const result = validateParcelForm(form({ area_sqm: 'abc' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.area_sqm).toBe('Area must be a number.');
  });

  it('rejects a status outside the allowed set', () => {
    const result = validateParcelForm(form({ status: 'sold' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.status).toBe('Select a valid status.');
  });

  describe('geometry (parsed client-side to avoid an opaque 500)', () => {
    it('rejects malformed JSON with a field-level message', () => {
      const result = validateParcelForm(form({ geometryText: '{not json' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toMatch(/Invalid JSON/);
    });

    it('rejects a JSON array, which the API dict type would not accept', () => {
      const result = validateParcelForm(form({ geometryText: '[]' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toMatch(/must be a JSON object/);
    });

    it('rejects an object without a type', () => {
      const result = validateParcelForm(form({ geometryText: '{"coordinates": []}' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toMatch(/"type"/);
    });

    it('rejects an object without coordinates', () => {
      const result = validateParcelForm(form({ geometryText: '{"type": "MultiPolygon"}' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toMatch(/"coordinates"/);
    });

    it('rejects non-array coordinates', () => {
      const result = validateParcelForm(form({ geometryText: '{"type": "MultiPolygon", "coordinates": 5}' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toMatch(/must be an array/);
    });

    it('requires geometry', () => {
      const result = validateParcelForm(form({ geometryText: '   ' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.geometryText).toBe('Geometry is required.');
    });
  });

  describe('metadata', () => {
    it('defaults to null when blank', () => {
      const result = validateParcelForm(form({ metadataText: '' }));

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.create.metadata).toBeNull();
    });

    it('parses a JSON object', () => {
      const result = validateParcelForm(form({ metadataText: '{"owner":"city"}' }));

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.create.metadata).toEqual({ owner: 'city' });
    });

    it('rejects malformed JSON', () => {
      const result = validateParcelForm(form({ metadataText: '{oops' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.metadataText).toMatch(/Invalid JSON/);
    });

    it('rejects a JSON array because the API type is an object', () => {
      const result = validateParcelForm(form({ metadataText: '[1,2]' }));

      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.errors.metadataText).toBe('Metadata must be a JSON object.');
    });
  });
});

describe('buildParcelUpdate', () => {
  const original: ParcelCreatePayload = {
    parcel_identifier: 'SEC-1',
    ulpin: 'ULPIN-1',
    geometry: VALID_GEOMETRY,
    area_sqm: 100,
    status: 'draft',
    metadata: null,
  };

  it('sends only the fields that changed', () => {
    const result = buildParcelUpdate(original, form({ status: 'active' }));

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({ status: 'active' });
  });

  it('returns an empty update when nothing changed', () => {
    const result = buildParcelUpdate(original, form());

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({});
  });

  it('sends several changed fields together', () => {
    const result = buildParcelUpdate(
      original,
      form({ status: 'active', area_sqm: '250', parcel_identifier: 'SEC-2' })
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({
      parcel_identifier: 'SEC-2',
      area_sqm: 250,
      status: 'active',
    });
  });

  it('detects a geometry change', () => {
    const changed = { type: 'MultiPolygon', coordinates: [[[[5, 5], [6, 5], [6, 6], [5, 5]]]] };
    const result = buildParcelUpdate(original, form({ geometryText: JSON.stringify(changed) }));

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({ geometry: changed });
  });

  it('propagates validation errors instead of sending an invalid update', () => {
    const result = buildParcelUpdate(original, form({ area_sqm: '-1' }));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.area_sqm).toBeTruthy();
  });

  it('does not report a change when only JSON key order differs', () => {
    const reordered = { coordinates: original.geometry.coordinates, type: original.geometry.type };
    const result = buildParcelUpdate(
      { ...original, geometry: reordered },
      form({ geometryText: JSON.stringify(original.geometry) })
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({});
  });

  it('does not report a metadata change when only JSON key order differs', () => {
    const result = buildParcelUpdate(
      { ...original, metadata: { a: 1, b: { c: 2, d: 3 } } },
      form({ metadataText: JSON.stringify({ b: { d: 3, c: 2 }, a: 1 }) })
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.update).toEqual({});
  });
});

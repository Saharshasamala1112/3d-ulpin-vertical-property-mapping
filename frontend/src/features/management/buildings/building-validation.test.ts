import { describe, it, expect } from 'vitest';
import {
  buildBuildingUpdate,
  emptyBuildingForm,
  validateBuildingForm,
  type BuildingFormValues,
} from './building-validation';

function form(overrides: Partial<BuildingFormValues> = {}): BuildingFormValues {
  return { ...emptyBuildingForm, building_identifier: 'BLD-1', ...overrides };
}

const polygon = { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] };

describe('building-validation', () => {
  describe('validateBuildingForm', () => {
    it('accepts a minimal valid form and sends null for a blank name', () => {
      const result = validateBuildingForm(form());
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.create).toEqual({
          building_identifier: 'BLD-1',
          name: null,
          building_type: 'residential',
          construction_status: 'planned',
          footprint_geometry: null,
        });
      }
    });

    it('trims the identifier and the name', () => {
      const result = validateBuildingForm(form({ building_identifier: '  BLD-9  ', name: '  Wing B  ' }));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.create.building_identifier).toBe('BLD-9');
        expect(result.create.name).toBe('Wing B');
      }
    });

    it('requires an identifier', () => {
      const result = validateBuildingForm(form({ building_identifier: '   ' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.building_identifier).toMatch(/required/i);
    });

    it('rejects an identifier longer than 255 characters', () => {
      const result = validateBuildingForm(form({ building_identifier: 'x'.repeat(256) }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.building_identifier).toMatch(/255/);
    });

    it('rejects an unknown building type', () => {
      const result = validateBuildingForm(form({ building_type: 'castle' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.building_type).toBeDefined();
    });

    it('rejects an unknown construction status', () => {
      const result = validateBuildingForm(form({ construction_status: 'haunted' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.construction_status).toBeDefined();
    });

    it('reports invalid footprint JSON against the footprint field', () => {
      const result = validateBuildingForm(form({ footprintText: '{not json' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.footprintText).toMatch(/invalid json/i);
    });

    it('rejects a footprint that is a JSON array', () => {
      const result = validateBuildingForm(form({ footprintText: '[]' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.footprintText).toMatch(/object/i);
    });

    it('accepts a valid GeoJSON polygon and keeps the object intact', () => {
      const result = validateBuildingForm(form({ footprintText: JSON.stringify(polygon) }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.create.footprint_geometry).toEqual(polygon);
    });

    it('treats blank footprint text as null rather than an error', () => {
      const result = validateBuildingForm(form({ footprintText: '   ' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.create.footprint_geometry).toBeNull();
    });
  });

  describe('buildBuildingUpdate', () => {
    const original = {
      building_identifier: 'BLD-1',
      name: 'Tower A',
      building_type: 'residential',
      construction_status: 'planned',
      footprint_geometry: null,
    };

    it('sends an empty payload when nothing changed', () => {
      const result = buildBuildingUpdate(original, form({ name: 'Tower A' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({});
    });

    it('sends only the changed field', () => {
      const result = buildBuildingUpdate(original, form({ name: 'Tower B' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ name: 'Tower B' });
    });

    it('sends name: null when the name is cleared', () => {
      const result = buildBuildingUpdate(original, form({ name: '' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ name: null });
    });

    it('sends footprint_geometry: null when the footprint is removed', () => {
      const withFootprint = { ...original, footprint_geometry: polygon };
      const result = buildBuildingUpdate(withFootprint, form({ name: 'Tower A', footprintText: '' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ footprint_geometry: null });
    });

    it('does not treat re-ordered JSON keys as a footprint change', () => {
      const reordered = { coordinates: polygon.coordinates, type: 'Polygon' };
      const result = buildBuildingUpdate(
        { ...original, footprint_geometry: reordered },
        form({ name: 'Tower A', footprintText: JSON.stringify(polygon) })
      );
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({});
    });

    it('returns validation errors instead of a partial update', () => {
      const result = buildBuildingUpdate(original, form({ building_identifier: '' }));
      expect(result.ok).toBe(false);
    });
  });
});

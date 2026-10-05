import { describe, it, expect } from 'vitest';
import {
  buildFloorUpdate,
  emptyFloorForm,
  validateFloorForm,
  type FloorFormValues,
} from './floor-validation';

function form(overrides: Partial<FloorFormValues> = {}): FloorFormValues {
  return { ...emptyFloorForm, floor_number: '1', elevation_min: '0', elevation_max: '3', ...overrides };
}

describe('floor-validation', () => {
  describe('validateFloorForm', () => {
    it('accepts a minimal valid form and sends null for a blank level name', () => {
      const result = validateFloorForm(form());
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.create).toEqual({
          floor_number: 1,
          level_name: null,
          floor_type: 'typical',
          elevation_min: 0,
          elevation_max: 3,
        });
      }
    });

    it('coerces a numeric floor number to a number, not a string', () => {
      const result = validateFloorForm(form({ floor_number: '12' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.create.floor_number).toBe(12);
    });

    it('accepts negative floor numbers for basements', () => {
      const result = validateFloorForm(form({ floor_number: '-1', floor_type: 'basement' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.create.floor_number).toBe(-1);
    });

    it('rejects a fractional floor number', () => {
      const result = validateFloorForm(form({ floor_number: '1.5' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.floor_number).toMatch(/whole number/i);
    });

    it('rejects a non-numeric floor number', () => {
      const result = validateFloorForm(form({ floor_number: 'ground' }));
      expect(result.ok).toBe(false);
    });

    it('requires both elevations', () => {
      const result = validateFloorForm(form({ elevation_min: '' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.elevation_min).toMatch(/required/i);
    });

    it('rejects a non-numeric elevation', () => {
      const result = validateFloorForm(form({ elevation_max: 'high' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.elevation_max).toMatch(/must be a number/i);
    });

    it('accepts zero and negative elevations', () => {
      const result = validateFloorForm(form({ elevation_min: '-3.5', elevation_max: '0' }));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.create.elevation_min).toBe(-3.5);
        expect(result.create.elevation_max).toBe(0);
      }
    });

    it('rejects an unknown floor type', () => {
      const result = validateFloorForm(form({ floor_type: 'attic' }));
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.floor_type).toBeDefined();
    });

    /**
     * The API has no validator on FloorCreate/FloorUpdate, so the UI must not
     * invent an ordering rule. Documenting it here means a future change to
     * `isStrictlyOrdered`-style validation on units is not copied here by
     * accident.
     */
    it('does not enforce elevation_min <= elevation_max, because the API does not', () => {
      const result = validateFloorForm(form({ elevation_min: '10', elevation_max: '2' }));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.create.elevation_min).toBe(10);
        expect(result.create.elevation_max).toBe(2);
      }
    });
  });

  describe('buildFloorUpdate', () => {
    const original = {
      floor_number: 1,
      level_name: 'Ground',
      floor_type: 'ground',
      elevation_min: 0,
      elevation_max: 3,
    };

    it('sends an empty payload when nothing changed', () => {
      const result = buildFloorUpdate(original, form({ floor_number: '1', level_name: 'Ground', floor_type: 'ground' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({});
    });

    it('sends only the changed field', () => {
      const result = buildFloorUpdate(original, form({ floor_number: '1', level_name: 'Lobby', floor_type: 'ground' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ level_name: 'Lobby' });
    });

    it('sends level_name: null when it is cleared', () => {
      const result = buildFloorUpdate(original, form({ floor_number: '1', level_name: '', floor_type: 'ground' }));
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.update).toEqual({ level_name: null });
    });

    it('returns validation errors rather than a partial update', () => {
      const result = buildFloorUpdate(original, form({ floor_number: '' }));
      expect(result.ok).toBe(false);
    });
  });
});

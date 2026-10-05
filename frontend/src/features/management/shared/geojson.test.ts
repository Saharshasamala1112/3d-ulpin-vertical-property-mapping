import { describe, it, expect } from 'vitest';
import { MULTI_POLYGON_TEMPLATE, parseGeoJsonText, stringifyGeoJson } from './geojson';

function parse(value: unknown) {
  return parseGeoJsonText(JSON.stringify(value));
}

describe('parseGeoJsonText', () => {
  describe('malformed input', () => {
    it('rejects blank text', () => {
      const result = parseGeoJsonText('   ');
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/required/i);
    });

    it('rejects invalid JSON with a parse-specific message', () => {
      const result = parseGeoJsonText('{not json');
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/invalid json/i);
    });

    it('rejects a JSON array', () => {
      const result = parse('[1,2,3]');
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/object/i);
    });

    it('rejects a geometry with no type', () => {
      const result = parse({ coordinates: [0, 0] });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/type/i);
    });
  });

  describe('known geometry types', () => {
    it('accepts a Point position', () => {
      expect(parse({ type: 'Point', coordinates: [12.97, 77.59] }).ok).toBe(true);
    });

    it('accepts a 3D position', () => {
      expect(parse({ type: 'Point', coordinates: [12.97, 77.59, 10] }).ok).toBe(true);
    });

    it('rejects a Point position with a single ordinate', () => {
      const result = parse({ type: 'Point', coordinates: [12.97] });
      expect(result.ok).toBe(false);
    });

    it('rejects a non-finite ordinate', () => {
      const result = parse({ type: 'Point', coordinates: [null, 77.59] });
      expect(result.ok).toBe(false);
    });

    it('accepts a MultiPoint', () => {
      expect(parse({ type: 'MultiPoint', coordinates: [[0, 0], [1, 1]] }).ok).toBe(true);
    });

    it('rejects a MultiPoint whose members are not positions', () => {
      const result = parse({ type: 'MultiPoint', coordinates: [[[0, 0]], [1, 1]] });
      expect(result.ok).toBe(false);
    });

    it('accepts a LineString', () => {
      expect(parse({ type: 'LineString', coordinates: [[0, 0], [1, 1]] }).ok).toBe(true);
    });

    it('accepts a Polygon with one closed ring', () => {
      const ring = [[0, 0], [1, 0], [1, 1], [0, 0]];
      expect(parse({ type: 'Polygon', coordinates: [ring] }).ok).toBe(true);
    });

    it('rejects a Polygon whose ring holds bare positions', () => {
      const result = parse({ type: 'Polygon', coordinates: [0, 0] });
      expect(result.ok).toBe(false);
    });

    it('accepts a MultiPolygon', () => {
      const ring = [[0, 0], [1, 0], [1, 1], [0, 0]];
      expect(parse({ type: 'MultiPolygon', coordinates: [[ring]] }).ok).toBe(true);
    });

    it('accepts the shipped template', () => {
      expect(parse(MULTI_POLYGON_TEMPLATE).ok).toBe(true);
    });
  });

  describe('nesting errors', () => {
    it('rejects empty coordinates', () => {
      const result = parse({ type: 'MultiPolygon', coordinates: [] });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/non-empty/i);
    });

    it('rejects an empty ring', () => {
      const result = parse({ type: 'Polygon', coordinates: [[]] });
      expect(result.ok).toBe(false);
    });

    it('catches the common mixed-depth paste error', () => {
      // First member is a bare ring where a polygon is required.
      const result = parse({
        type: 'MultiPolygon',
        coordinates: [
          [[0, 0], [1, 0], [0, 0]],
          [[[2, 2], [3, 2], [2, 2]]],
        ],
      });
      expect(result.ok).toBe(false);
    });

    it('catches a member that is one level too deep', () => {
      const result = parse({
        type: 'Polygon',
        coordinates: [[[[0, 0], [1, 0], [0, 0]]]],
      });
      expect(result.ok).toBe(false);
    });

    it('points at the offending index', () => {
      const result = parse({ type: 'MultiPoint', coordinates: [[0, 0], [1]] });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toContain('[1]');
    });

    it('rejects a ring that is too shallow for a MultiPolygon', () => {
      const result = parse({ type: 'MultiPolygon', coordinates: [[[0, 0], [1, 0]]] });
      expect(result.ok).toBe(false);
    });
  });

  describe('unknown geometry types', () => {
    it('still requires a coordinates member', () => {
      const result = parse({ type: 'GeometryCollection' });
      expect(result.ok).toBe(false);
    });

    it('rejects a real GeometryCollection because it nests geometries, not coordinates', () => {
      // Known UI limitation, documented in docs/property-management.md: a valid
      // GeoJSON GeometryCollection cannot be entered and must be flattened to a
      // MultiPolygon or MultiLineString first.
      const result = parse({
        type: 'GeometryCollection',
        geometries: [{ type: 'Point', coordinates: [1, 2] }],
      });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/coordinates/);
    });

    it('falls back to structure-only validation rather than guessing a depth', () => {
      // The depth is unknown, so nesting is not enforced, but it must still be
      // an object with a string type.
      const result = parse({ type: 'Sphere', coordinates: [0, 0, 100] });
      expect(result.ok).toBe(true);
    });
  });
});

describe('stringifyGeoJson', () => {
  it('produces indented, parseable JSON', () => {
    const text = stringifyGeoJson({ type: 'Point', coordinates: [1, 2] });
    expect(text).toContain('\n');
    expect(parseGeoJsonText(text).ok).toBe(true);
  });

  it('round-trips the template back to an equal object', () => {
    const reparsed = parseGeoJsonText(stringifyGeoJson(MULTI_POLYGON_TEMPLATE));
    expect(reparsed.ok).toBe(true);
    if (reparsed.ok) expect(reparsed.value).toEqual(MULTI_POLYGON_TEMPLATE);
  });
});

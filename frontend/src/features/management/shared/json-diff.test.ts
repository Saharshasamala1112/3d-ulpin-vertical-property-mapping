import { describe, it, expect } from 'vitest';
import { isJsonEqual } from './json-diff';

describe('isJsonEqual', () => {
  it('treats identical primitives as equal', () => {
    expect(isJsonEqual(1, 1)).toBe(true);
    expect(isJsonEqual('a', 'b')).toBe(false);
  });

  it('is key-order insensitive at the top level', () => {
    expect(isJsonEqual({ a: 1, b: 2 }, { b: 2, a: 1 })).toBe(true);
  });

  it('is key-order insensitive in nested objects', () => {
    expect(
      isJsonEqual(
        { type: 'Polygon', coordinates: [[[0, 0], { x: 1, y: 0 }]] },
        { coordinates: [[[0, 0], { y: 0, x: 1 }]], type: 'Polygon' }
      )
    ).toBe(true);
  });

  it('is array-order sensitive, because GeoJSON rings are ordered', () => {
    expect(isJsonEqual([1, 2], [2, 1])).toBe(false);
  });

  it('distinguishes null from an empty object', () => {
    expect(isJsonEqual(null, {})).toBe(false);
  });

  it('distinguishes a missing key from an explicit null', () => {
    expect(isJsonEqual({}, { a: null })).toBe(false);
  });

  it('detects a genuine nested change', () => {
    expect(isJsonEqual({ a: { b: [1, 2] } }, { a: { b: [1, 3] } })).toBe(false);
  });
});

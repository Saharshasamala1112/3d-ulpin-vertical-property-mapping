import { describe, it, expect } from 'vitest';
import { FLOOR_COLORS, floorColor } from './viewer-colors';

describe('floorColor', () => {
  it('gives each floor index its own colour', () => {
    for (let index = 0; index < FLOOR_COLORS.length; index += 1) {
      expect(floorColor(index)).toBe(FLOOR_COLORS[index]);
    }
  });

  it('is stable for the same index', () => {
    expect(floorColor(3)).toBe(floorColor(3));
  });

  it('wraps around so tall buildings stay renderable', () => {
    expect(floorColor(FLOOR_COLORS.length)).toBe(FLOOR_COLORS[0]);
    expect(floorColor(FLOOR_COLORS.length * 2 + 1)).toBe(FLOOR_COLORS[1]);
  });

  it('handles a negative index instead of returning undefined', () => {
    // A unit whose floor is missing from the scene resolves to -1.
    expect(FLOOR_COLORS).toContain(floorColor(-1));
  });

  it('always returns a valid hex colour', () => {
    for (let index = -5; index < FLOOR_COLORS.length * 3; index += 1) {
      expect(floorColor(index)).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});

import { describe, it, expect } from 'vitest';
import {
  applyOrbitDelta,
  applyZoomDelta,
  clamp,
  computeSceneFocus,
  groundHeight,
  initialSpherical,
  safeDimension,
  type Spherical,
} from './orbit';
import type { SceneUnit } from '../../types/geometry';

function makeUnit(
  id: string,
  min: [number, number, number],
  max: [number, number, number],
  floorId = 'f-1',
): SceneUnit {
  return {
    id,
    unitIdentifier: id,
    unitType: 'residential',
    status: 'active',
    floor: { id: floorId, floorNumber: 1, levelName: 'Ground', floorType: 'ground' },
    geometry: {
      id: `geo-${id}`,
      unitId: id,
      geometryType: 'aabb',
      bounds: {
        min: { x: min[0], y: min[1], z: min[2] },
        max: { x: max[0], y: max[1], z: max[2] },
      },
      centroid: {
        x: (min[0] + max[0]) / 2,
        y: (min[1] + max[1]) / 2,
        z: (min[2] + max[2]) / 2,
      },
      dimensions: {
        x: max[0] - min[0],
        y: max[1] - min[1],
        z: max[2] - min[2],
      },
      volume: (max[0] - min[0]) * (max[1] - min[1]) * (max[2] - min[2]),
      createdAt: '',
      updatedAt: '',
    },
  };
}

describe('clamp', () => {
  it('bounds a value', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(50, 0, 10)).toBe(10);
  });
});

describe('applyOrbitDelta', () => {
  const base: Spherical = { radius: 20, phi: Math.PI / 3, theta: Math.PI / 4 };

  it('rotates horizontally without changing radius or elevation', () => {
    const next = applyOrbitDelta(base, 100, 0);
    expect(next.theta).toBeLessThan(base.theta);
    expect(next.phi).toBe(base.phi);
    expect(next.radius).toBe(base.radius);
  });

  it('raises the camera as the pointer moves down', () => {
    // Matches the three.js OrbitControls convention: dragging down decreases
    // the polar angle, and since camera z = radius * cos(phi) that lifts the
    // camera so you look down onto the model.
    const next = applyOrbitDelta(base, 0, 50);
    expect(next.phi).toBeLessThan(base.phi);
  });

  it('lowers the camera as the pointer moves up', () => {
    const next = applyOrbitDelta(base, 0, -50);
    expect(next.phi).toBeGreaterThan(base.phi);
  });

  it('never flips over the poles', () => {
    let state = base;
    for (let i = 0; i < 200; i += 1) state = applyOrbitDelta(state, 0, 500);
    expect(state.phi).toBeLessThan(Math.PI);
    expect(state.phi).toBeGreaterThan(0);

    let flipped = base;
    for (let i = 0; i < 200; i += 1) flipped = applyOrbitDelta(flipped, 0, -500);
    expect(flipped.phi).toBeGreaterThan(0);
  });
});

describe('applyZoomDelta', () => {
  it('zooms out on a positive delta and in on a negative one', () => {
    const base: Spherical = { radius: 20, phi: 1, theta: 1 };
    expect(applyZoomDelta(base, 100).radius).toBeGreaterThan(base.radius);
    expect(applyZoomDelta(base, -100).radius).toBeLessThan(base.radius);
  });

  it('respects the distance clamp', () => {
    const base: Spherical = { radius: 20, phi: 1, theta: 1 };
    expect(applyZoomDelta(base, -10000, 5, 50).radius).toBe(5);
    expect(applyZoomDelta(base, 10000, 5, 50).radius).toBe(50);
  });

  it('does not mutate the input', () => {
    const base: Spherical = { radius: 20, phi: 1, theta: 1 };
    applyZoomDelta(base, 100);
    expect(base.radius).toBe(20);
  });
});

describe('initialSpherical', () => {
  it('starts outside the scene with a downward-looking elevation', () => {
    const state = initialSpherical(10);
    expect(state.radius).toBeGreaterThan(10);
    expect(state.phi).toBeGreaterThan(0);
    expect(state.phi).toBeLessThan(Math.PI / 2);
  });
});

describe('computeSceneFocus', () => {
  it('centres on the bounding box of every unit', () => {
    const units = [
      makeUnit('a', [0, 0, 0], [2, 2, 3]),
      makeUnit('b', [8, 4, 0], [10, 6, 3]),
    ];

    const focus = computeSceneFocus(units);

    expect(focus.center).toEqual({ x: 5, y: 3, z: 1.5 });
    // diagonal is sqrt(10^2 + 6^2 + 3^2) = sqrt(145) ~= 12.04, half * 1.1
    expect(focus.radius).toBeCloseTo((Math.hypot(10, 6, 3) / 2) * 1.1, 5);
  });

  it('uses bounds rather than centroids so one large unit still frames the scene', () => {
    const wide = makeUnit('a', [-50, 0, 0], [50, 1, 1]);
    const focus = computeSceneFocus([wide]);
    expect(focus.radius).toBeGreaterThan(45);
  });

  it('never returns a zero radius for a tiny or empty scene', () => {
    expect(computeSceneFocus([makeUnit('a', [0, 0, 0], [0.001, 0.001, 0.001])]).radius).toBeGreaterThan(0);
    const empty = computeSceneFocus([]);
    expect(empty).toEqual({ center: { x: 0, y: 0, z: 0 }, radius: 10 });
  });
});

describe('groundHeight', () => {
  it('reports the lowest point in the scene', () => {
    const units = [makeUnit('a', [0, 0, 0.5], [1, 1, 3]), makeUnit('b', [0, 0, 2], [1, 1, 5])];
    expect(groundHeight(units)).toBe(0.5);
  });

  it('falls back to zero with no units', () => {
    expect(groundHeight([])).toBe(0);
  });
});

describe('safeDimension', () => {
  it('passes through positive extents', () => {
    expect(safeDimension(4.530865)).toBe(4.530865);
  });

  it('replaces zero, negative and non-finite extents so the box is never degenerate', () => {
    expect(safeDimension(0)).toBe(0.01);
    expect(safeDimension(-2)).toBe(0.01);
    expect(safeDimension(Number.NaN)).toBe(0.01);
  });
});

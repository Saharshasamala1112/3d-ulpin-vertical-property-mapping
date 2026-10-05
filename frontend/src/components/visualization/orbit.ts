import type { SceneUnit, Vec3 } from '../../types/geometry';

/**
 * Camera maths for the viewer.
 *
 * These helpers are deliberately free of React and three.js so the framing and
 * orbit behaviour can be unit tested in jsdom, which has no WebGL context.
 *
 * The viewer uses a Z-up convention: the geometry API's `z_min`/`z_max` are
 * heights, so they map straight onto three's Z axis rather than being rotated
 * into three's default Y-up.
 */

const MIN_PHI = 0.01;
const MAX_PHI = Math.PI - 0.01;
const ROTATE_SPEED = 0.005;
const ZOOM_SPEED = 0.001;

export interface Spherical {
  radius: number;
  phi: number;
  theta: number;
}

export interface SceneFocus {
  center: Vec3;
  radius: number;
}

const MIN_RADIUS = 1;
const FALLBACK_RADIUS = 10;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function applyOrbitDelta(spherical: Spherical, deltaX: number, deltaY: number): Spherical {
  return {
    radius: spherical.radius,
    theta: spherical.theta - deltaX * ROTATE_SPEED,
    phi: clamp(spherical.phi - deltaY * ROTATE_SPEED, MIN_PHI, MAX_PHI),
  };
}

export function applyZoomDelta(spherical: Spherical, deltaY: number, min = MIN_RADIUS, max = Number.MAX_SAFE_INTEGER): Spherical {
  return {
    ...spherical,
    radius: clamp(spherical.radius * Math.exp(deltaY * ZOOM_SPEED), min, max),
  };
}

export function initialSpherical(radius: number): Spherical {
  // Slightly above the horizon, looking down at ~45 degrees.
  return { radius: radius * 1.6, phi: Math.PI / 3, theta: Math.PI / 4 };
}

/**
 * Bounding sphere that frames the whole scene.
 *
 * Uses the unit bounds rather than centroids so a scene with few but large
 * units is still framed correctly.
 */
export function computeSceneFocus(units: SceneUnit[]): SceneFocus {
  if (units.length === 0) {
    return { center: { x: 0, y: 0, z: 0 }, radius: FALLBACK_RADIUS };
  }

  const min = { x: Infinity, y: Infinity, z: Infinity };
  const max = { x: -Infinity, y: -Infinity, z: -Infinity };

  for (const unit of units) {
    const { bounds } = unit.geometry;
    min.x = Math.min(min.x, bounds.min.x);
    min.y = Math.min(min.y, bounds.min.y);
    min.z = Math.min(min.z, bounds.min.z);
    max.x = Math.max(max.x, bounds.max.x);
    max.y = Math.max(max.y, bounds.max.y);
    max.z = Math.max(max.z, bounds.max.z);
  }

  const size = { x: max.x - min.x, y: max.y - min.y, z: max.z - min.z };

  return {
    center: {
      x: (min.x + max.x) / 2,
      y: (min.y + max.y) / 2,
      z: (min.z + max.z) / 2,
    },
    radius: Math.max((Math.hypot(size.x, size.y, size.z) / 2) * 1.1, MIN_RADIUS),
  };
}

/** Ground plane height for the grid: the lowest point in the scene. */
export function groundHeight(units: SceneUnit[]): number {
  if (units.length === 0) return 0;
  return Math.min(...units.map((unit) => unit.geometry.bounds.min.z));
}

/**
 * Guard against a zero-extent axis producing a degenerate box geometry.
 * The database CHECK constraint keeps `min < max`, but a viewer should not
 * crash on unexpected data from another writer.
 */
export function safeDimension(value: number): number {
  return Number.isFinite(value) && value > 0 ? value : 0.01;
}

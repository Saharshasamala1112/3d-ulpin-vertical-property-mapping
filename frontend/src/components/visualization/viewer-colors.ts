/**
 * Colours shared by the page chrome and the 3D canvas.
 *
 * Kept in its own module so the page can colour-code floors without importing
 * `GeometryViewer`, which would pull three.js into the initial bundle.
 */

/** One colour per floor so stacked levels stay distinguishable. */
export const FLOOR_COLORS = [
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#dc2626',
  '#9333ea',
  '#0891b2',
  '#db2777',
  '#65a30d',
  '#7c3aed',
  '#ea580c',
] as const;

export function floorColor(index: number): string {
  return FLOOR_COLORS[((index % FLOOR_COLORS.length) + FLOOR_COLORS.length) % FLOOR_COLORS.length];
}

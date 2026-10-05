/**
 * Structural JSON comparison for partial-update diffing.
 *
 * `JSON.stringify` is key-order sensitive, so a user who only reformats a
 * GeoJSON or metadata blob (or whose serializer emits keys in a different
 * order than the server did) would otherwise produce a spurious update. A
 * no-op save should send an empty payload.
 */
function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }
  if (value !== null && typeof value === 'object') {
    const source = value as Record<string, unknown>;
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(source).sort()) {
      result[key] = canonicalize(source[key]);
    }
    return result;
  }
  return value;
}

export function isJsonEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  return JSON.stringify(canonicalize(a)) === JSON.stringify(canonicalize(b));
}

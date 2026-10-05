import { describeSegment, describeVdcError } from './vdc-validation';
import type { VdcValidationError } from './vdc-types';

interface VdcErrorListProps {
  errors: VdcValidationError[];
}

/**
 * Renders the backend's per-segment validation errors.
 *
 * The raw code is always shown, so an unmapped code stays visible instead of
 * being silently dropped, and each entry names the segment it refers to.
 */
export function VdcErrorList({ errors }: VdcErrorListProps) {
  if (errors.length === 0) return null;

  return (
    <ul
      aria-label="VDC validation errors"
      style={{ margin: 0, paddingLeft: '1.125rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}
    >
      {errors.map((error, index) => {
        const described = describeVdcError(error);
        return (
          <li key={`${described.code}-${described.segment}-${index}`} style={{ fontSize: '0.8125rem' }}>
            <span style={{ fontWeight: 600 }}>{describeSegment(described.segment)}</span>
            {' — '}
            <span>{described.label}</span>
            {' ('}
            <code style={{ fontSize: '0.75rem' }}>{described.code}</code>
            {')'}
            {described.message ? `: ${described.message}` : ''}
          </li>
        );
      })}
    </ul>
  );
}

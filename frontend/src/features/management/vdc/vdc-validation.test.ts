import { describe, it, expect } from 'vitest';
import { ApiError } from '../../../services/api-error';
import { describeSegment, describeVdcError, extractVdcErrors } from './vdc-validation';
import type { VdcValidationError } from './vdc-types';

function vdcError(overrides: Partial<VdcValidationError> = {}): VdcValidationError {
  return {
    segment: 'ulpin',
    code: 'invalid_ulpin',
    message: 'ULPIN must match GEOSX + 5 digits',
    ...overrides,
  };
}

/** Build the ApiError the way a real 422 parse failure arrives. */
function parseFailure(errors: unknown[]) {
  return new ApiError({
    status: 422,
    errorCode: 'VALIDATION_ERROR',
    message: 'Request validation failed',
    details: { vdc_errors: errors },
  });
}

describe('vdc-validation', () => {
  describe('extractVdcErrors', () => {
    it('reads the structured errors off a 422 parse failure', () => {
      const error = parseFailure([vdcError()]);
      expect(extractVdcErrors(error)).toEqual([
        {
          segment: 'ulpin',
          code: 'invalid_ulpin',
          message: 'ULPIN must match GEOSX + 5 digits',
        },
      ]);
    });

    it('returns an empty list when the payload has no structured errors', () => {
      const error = new ApiError({ status: 500, errorCode: 'INTERNAL_ERROR', message: 'boom' });
      expect(extractVdcErrors(error)).toEqual([]);
    });

    it('skips malformed entries rather than rendering undefined fields', () => {
      const error = parseFailure([vdcError(), { segment: 'unit' }, null, 'nope', 42]);
      expect(extractVdcErrors(error)).toHaveLength(1);
    });
  });

  describe('describeVdcError', () => {
    it('translates every code the backend can emit', () => {
      const codes = [
        'lowercase_character',
        'invalid_character',
        'invalid_ulpin',
        'invalid_domain',
        'invalid_level',
        'invalid_unit',
        'invalid_checksum',
        'invalid_segment_count',
        'empty_segment',
        'checksum_mismatch',
      ];

      for (const code of codes) {
        const described = describeVdcError(vdcError({ code }));
        expect(described.label, code).not.toContain('Unrecognised');
        expect(described.unknown, code).toBe(false);
        expect(described.label.length, code).toBeGreaterThan(0);
      }
    });

    it('names the checksum failure explicitly', () => {
      const described = describeVdcError(
        vdcError({ segment: 'checksum', code: 'checksum_mismatch', message: 'Checksum mismatch' }),
      );
      expect(described.segment).toBe('checksum');
      expect(described.label).toBe('Checksum mismatch');
      expect(described.structural).toBe(false);
    });

    it('keeps an unknown code visible instead of dropping it', () => {
      const described = describeVdcError(vdcError({ code: 'some_future_check' }));
      expect(described.unknown).toBe(true);
      expect(described.code).toBe('some_future_check');
      expect(described.label).toContain('some_future_check');
    });

    it('flags whole-code structural problems', () => {
      const described = describeVdcError(
        vdcError({ segment: 'structure', code: 'invalid_segment_count' }),
      );
      expect(described.structural).toBe(true);
    });
  });

  describe('describeSegment', () => {
    it('upper-cases a segment name', () => {
      expect(describeSegment('ulpin')).toBe('ULPIN');
    });

    it('gives the structural pseudo-segment a readable name', () => {
      expect(describeSegment('structure')).toBe('Code structure');
    });
  });
});

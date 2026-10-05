import { describe, it, expect, beforeEach } from 'vitest';
import {
  UNIT_VALIDATION_STATUS_KEY,
  buildUnitValidationStatusHandoff,
  clearUnitValidationStatusHandoff,
  publishUnitValidationStatusHandoff,
  readUnitValidationStatusHandoff,
} from './unit-validation-status';
import type { TopologyValidationReport } from '../types/topology';

const UNIT_A = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';

function passingReport(): TopologyValidationReport {
  return {
    summary: {
      status: 'passed',
      valid: true,
      geometry_error_count: 0,
      overlap_count: 0,
      gap_count: 0,
      elevation_error_count: 0,
    },
    geometry_errors: [],
    overlap_results: [],
    gap_results: [],
    elevation_errors: [],
  };
}

describe('unit validation status handoff', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('builds a handoff with scope, target, and statuses', () => {
    const handoff = buildUnitValidationStatusHandoff({
      report: passingReport(),
      scope: 'building',
      targetId: 'building-1',
      knownUnitIds: [UNIT_A],
    });

    expect(handoff.scope).toBe('building');
    expect(handoff.target_id).toBe('building-1');
    expect(handoff.statuses[UNIT_A]).toBe('valid');
    expect(typeof handoff.generated_at).toBe('string');
  });

  it('publishes and reads the handoff through sessionStorage', () => {
    const handoff = buildUnitValidationStatusHandoff({
      report: passingReport(),
      scope: 'unit',
      targetId: UNIT_A,
      knownUnitIds: [UNIT_A],
    });

    publishUnitValidationStatusHandoff(handoff);

    expect(sessionStorage.getItem(UNIT_VALIDATION_STATUS_KEY)).toBeTruthy();
    expect(readUnitValidationStatusHandoff()?.target_id).toBe(UNIT_A);
  });

  it('clears the published handoff', () => {
    publishUnitValidationStatusHandoff(
      buildUnitValidationStatusHandoff({
        report: passingReport(),
        scope: 'unit',
        targetId: UNIT_A,
      })
    );
    clearUnitValidationStatusHandoff();
    expect(readUnitValidationStatusHandoff()).toBeNull();
  });

  it('returns null for corrupt stored data', () => {
    sessionStorage.setItem(UNIT_VALIDATION_STATUS_KEY, 'not-json');
    expect(readUnitValidationStatusHandoff()).toBeNull();
    sessionStorage.setItem(UNIT_VALIDATION_STATUS_KEY, JSON.stringify({ nope: true }));
    expect(readUnitValidationStatusHandoff()).toBeNull();
  });
});

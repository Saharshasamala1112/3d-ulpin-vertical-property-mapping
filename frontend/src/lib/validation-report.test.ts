import { describe, it, expect } from 'vitest';
import {
  affectedUnitIds,
  deriveUnitStatuses,
  issuesByCategory,
  severityLabel,
} from './validation-report';
import type { TopologyValidationReport } from '../types/topology';

const UNIT_A = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';
const UNIT_B = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const UNIT_C = 'cccccccc-3333-4333-8333-cccccccccccc';

function baseReport(): TopologyValidationReport {
  return {
    summary: {
      status: 'failed',
      valid: false,
      geometry_error_count: 1,
      overlap_count: 1,
      gap_count: 1,
      elevation_error_count: 1,
    },
    geometry_errors: [
      {
        unit_id: UNIT_A,
        code: 'MISSING_GEOMETRY',
        message: 'Unit has no 3D geometry',
        field: 'geometry',
      },
    ],
    overlap_results: [
      {
        unit_a_id: UNIT_B,
        unit_b_id: UNIT_C,
        overlap_volume: '12.5',
        overlap_geometry: {
          x_min: '0',
          x_max: '1',
          y_min: '0',
          y_max: '1',
          z_min: '0',
          z_max: '1',
        },
      },
    ],
    gap_results: [
      {
        unit_a_id: UNIT_A,
        unit_b_id: UNIT_B,
        gap_distance: '0.25',
        gap_direction: 'x',
        gap_geometry: {
          x_min: '0',
          x_max: '0.25',
          y_min: '0',
          y_max: '1',
          z_min: '0',
          z_max: '1',
        },
      },
    ],
    elevation_errors: [
      {
        code: 'UNIT_ELEVATION_OUT_OF_BOUNDS',
        message: 'Unit elevation falls outside the floor range',
        floor_id: 'floor-1',
        unit_id: UNIT_C,
      },
    ],
  };
}

describe('issuesByCategory', () => {
  it('groups every report entry under its category', () => {
    const grouped = issuesByCategory(baseReport());
    expect(grouped.geometry).toHaveLength(1);
    expect(grouped.overlap).toHaveLength(1);
    expect(grouped.gap).toHaveLength(1);
    expect(grouped.elevation).toHaveLength(1);
  });

  it('describes overlap issues with both unit ids and volume detail', () => {
    const [issue] = issuesByCategory(baseReport()).overlap;
    expect(issue.severity).toBe('critical');
    expect(issue.unitIds).toEqual([UNIT_B, UNIT_C]);
    expect(issue.message).toContain(UNIT_B.slice(0, 8));
    expect(issue.details.find((d) => d.label === 'Overlap volume')?.value).toBe('12.5');
  });

  it('describes gap issues with distance and direction details', () => {
    const [issue] = issuesByCategory(baseReport()).gap;
    expect(issue.message).toContain('0.25');
    expect(issue.message).toContain('x axis');
    expect(issue.details.find((d) => d.label === 'Gap direction')?.value).toBe('X');
  });

  it('labels severities', () => {
    expect(severityLabel('critical')).toBe('Critical');
    expect(severityLabel('warning')).toBe('Warning');
  });
});

describe('affectedUnitIds', () => {
  it('returns sorted unique unit ids across categories', () => {
    expect(affectedUnitIds(baseReport())).toEqual([UNIT_A, UNIT_B, UNIT_C].sort());
  });

  it('returns an empty list for a clean report', () => {
    const report = baseReport();
    report.geometry_errors = [];
    report.overlap_results = [];
    report.gap_results = [];
    report.elevation_errors = [];
    expect(affectedUnitIds(report)).toEqual([]);
  });
});

describe('deriveUnitStatuses', () => {
  it('marks known units without issues as valid', () => {
    const report = baseReport();
    const statuses = deriveUnitStatuses(report, [UNIT_A, UNIT_B, 'valid-unit']);
    expect(statuses['valid-unit']).toBe('valid');
  });

  it('applies category statuses to affected units', () => {
    const statuses = deriveUnitStatuses(baseReport(), [UNIT_A, UNIT_B, UNIT_C]);
    expect(statuses[UNIT_B]).toBe('overlap');
    expect(statuses[UNIT_C]).toBe('overlap');
    expect(statuses[UNIT_A]).toBe('gap');
  });

  it('ranks overlap above other statuses for the same unit', () => {
    const report = baseReport();
    report.gap_results[0].unit_a_id = UNIT_B;
    const statuses = deriveUnitStatuses(report, [UNIT_B]);
    expect(statuses[UNIT_B]).toBe('overlap');
  });

  it('marks geometry errors when no higher status applies', () => {
    const report = baseReport();
    report.gap_results = [];
    const statuses = deriveUnitStatuses(report, [UNIT_A]);
    expect(statuses[UNIT_A]).toBe('geometry_error');
  });

  it('ignores elevation errors without a unit id', () => {
    const report = baseReport();
    report.elevation_errors[0].unit_id = null;
    report.geometry_errors = [];
    report.overlap_results = [];
    report.gap_results = [];
    const statuses = deriveUnitStatuses(report, []);
    expect(Object.keys(statuses)).toEqual([]);
  });
});

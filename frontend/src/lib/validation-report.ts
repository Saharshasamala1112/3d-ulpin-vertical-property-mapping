import type {
  GapResult,
  IssueCategory,
  IssueSeverity,
  TopologyValidationReport,
  UnitValidationStatus,
  ValidationIssue,
} from '../types/topology';

export const CATEGORIES: readonly IssueCategory[] = [
  'geometry',
  'overlap',
  'gap',
  'elevation',
] as const;

export const CATEGORY_LABELS: Record<IssueCategory, string> = {
  geometry: 'Geometry validity',
  overlap: 'Volumetric overlap',
  gap: 'Spatial gap',
  elevation: 'Floor & elevation consistency',
};

export const CATEGORY_DESCRIPTIONS: Record<IssueCategory, string> = {
  geometry: 'Missing, invalid, or unsupported 3D property geometry',
  overlap: 'Units whose bounding boxes intersect in volume',
  gap: 'Unoccupied gaps between otherwise adjacent units',
  elevation: 'Unit elevations that fall outside their floor bounds',
};

export const SEVERITY_BY_CATEGORY: Record<IssueCategory, IssueSeverity> = {
  geometry: 'error',
  overlap: 'critical',
  gap: 'warning',
  elevation: 'warning',
};

const SEVERITY_LABELS: Record<IssueSeverity, string> = {
  critical: 'Critical',
  error: 'Error',
  warning: 'Warning',
};

const STATUS_RANK: Record<UnitValidationStatus, number> = {
  valid: 0,
  geometry_error: 1,
  elevation: 2,
  gap: 3,
  overlap: 4,
};

export function severityLabel(severity: IssueSeverity): string {
  return SEVERITY_LABELS[severity];
}

export function shortId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

function rangeLabel(box: {
  x_min: string;
  x_max: string;
  y_min: string;
  y_max: string;
  z_min: string;
  z_max: string;
}): string {
  return `x ${box.x_min}→${box.x_max}, y ${box.y_min}→${box.y_max}, z ${box.z_min}→${box.z_max}`;
}

function pairMessage(result: GapResult | { unit_a_id: string; unit_b_id: string }, body: string): string {
  return `Units ${shortId(result.unit_a_id)} and ${shortId(result.unit_b_id)} ${body}.`;
}

function buildIssues(report: TopologyValidationReport): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  report.geometry_errors.forEach((error, index) => {
    issues.push({
      id: `geometry-${index}`,
      category: 'geometry',
      severity: SEVERITY_BY_CATEGORY.geometry,
      code: error.code,
      message: error.message,
      unitIds: [error.unit_id],
      details: [{ label: 'Field', value: error.field }],
    });
  });

  report.overlap_results.forEach((overlap, index) => {
    issues.push({
      id: `overlap-${index}`,
      category: 'overlap',
      severity: SEVERITY_BY_CATEGORY.overlap,
      code: 'OVERLAP',
      message: pairMessage(
        overlap,
        `overlap with volume ${overlap.overlap_volume}`
      ),
      unitIds: [overlap.unit_a_id, overlap.unit_b_id],
      details: [
        { label: 'Overlap volume', value: overlap.overlap_volume },
        { label: 'Overlap bounds', value: rangeLabel(overlap.overlap_geometry) },
      ],
    });
  });

  report.gap_results.forEach((gap, index) => {
    issues.push({
      id: `gap-${index}`,
      category: 'gap',
      severity: SEVERITY_BY_CATEGORY.gap,
      code: 'GAP',
      message: pairMessage(
        gap,
        `have a ${gap.gap_distance} gap along the ${gap.gap_direction} axis`
      ),
      unitIds: [gap.unit_a_id, gap.unit_b_id],
      details: [
        { label: 'Gap distance', value: gap.gap_distance },
        { label: 'Gap direction', value: gap.gap_direction.toUpperCase() },
        { label: 'Gap bounds', value: rangeLabel(gap.gap_geometry) },
      ],
    });
  });

  report.elevation_errors.forEach((error, index) => {
    issues.push({
      id: `elevation-${index}`,
      category: 'elevation',
      severity: SEVERITY_BY_CATEGORY.elevation,
      code: error.code,
      message: error.message,
      unitIds: error.unit_id ? [error.unit_id] : [],
      details: error.floor_id ? [{ label: 'Floor', value: error.floor_id }] : [],
    });
  });

  return issues;
}

export function issuesByCategory(
  report: TopologyValidationReport
): Record<IssueCategory, ValidationIssue[]> {
  const grouped: Record<IssueCategory, ValidationIssue[]> = {
    geometry: [],
    overlap: [],
    gap: [],
    elevation: [],
  };
  for (const issue of buildIssues(report)) {
    grouped[issue.category].push(issue);
  }
  return grouped;
}

export function affectedUnitIds(report: TopologyValidationReport): string[] {
  const ids = new Set<string>();
  for (const issue of buildIssues(report)) {
    for (const unitId of issue.unitIds) ids.add(unitId);
  }
  return [...ids].sort();
}

export function deriveUnitStatuses(
  report: TopologyValidationReport,
  knownUnitIds: string[] = []
): Record<string, UnitValidationStatus> {
  const statuses: Record<string, UnitValidationStatus> = {};
  for (const unitId of knownUnitIds) statuses[unitId] = 'valid';

  const apply = (unitIds: string[], status: UnitValidationStatus) => {
    for (const unitId of unitIds) {
      const current = statuses[unitId];
      if (!current || STATUS_RANK[status] > STATUS_RANK[current]) {
        statuses[unitId] = status;
      }
    }
  };

  for (const issue of buildIssues(report)) {
    if (issue.category === 'elevation') apply(issue.unitIds, 'elevation');
    else if (issue.category === 'gap') apply(issue.unitIds, 'gap');
    else if (issue.category === 'overlap') apply(issue.unitIds, 'overlap');
    else apply(issue.unitIds, 'geometry_error');
  }

  return statuses;
}

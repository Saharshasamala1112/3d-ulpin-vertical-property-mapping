export type ValidationRunStatus = 'passed' | 'failed';

export interface ValidationSummary {
  status: ValidationRunStatus;
  valid: boolean;
  geometry_error_count: number;
  overlap_count: number;
  gap_count: number;
  elevation_error_count: number;
}

export interface GeometryValidationError {
  unit_id: string;
  code: string;
  message: string;
  field: string;
}

export interface ValidationBoundingBox {
  x_min: string;
  x_max: string;
  y_min: string;
  y_max: string;
  z_min: string;
  z_max: string;
}

export interface OverlapResult {
  unit_a_id: string;
  unit_b_id: string;
  overlap_volume: string;
  overlap_geometry: ValidationBoundingBox;
}

export interface GapResult {
  unit_a_id: string;
  unit_b_id: string;
  gap_distance: string;
  gap_direction: 'x' | 'y' | 'z';
  gap_geometry: ValidationBoundingBox;
}

export interface ElevationValidationError {
  code: string;
  message: string;
  floor_id: string | null;
  unit_id: string | null;
}

export interface TopologyValidationReport {
  summary: ValidationSummary;
  geometry_errors: GeometryValidationError[];
  overlap_results: OverlapResult[];
  gap_results: GapResult[];
  elevation_errors: ElevationValidationError[];
}

export type IssueCategory = 'geometry' | 'overlap' | 'gap' | 'elevation';

export type IssueSeverity = 'critical' | 'error' | 'warning';

export interface ValidationIssueDetail {
  label: string;
  value: string;
}

export interface ValidationIssue {
  id: string;
  category: IssueCategory;
  severity: IssueSeverity;
  code: string;
  message: string;
  unitIds: string[];
  details: ValidationIssueDetail[];
}

export type UnitValidationStatus =
  | 'valid'
  | 'overlap'
  | 'gap'
  | 'elevation'
  | 'geometry_error';

export type ValidationScope = 'building' | 'unit';

export interface ValidationTarget {
  buildingId?: string;
  unitId?: string;
}

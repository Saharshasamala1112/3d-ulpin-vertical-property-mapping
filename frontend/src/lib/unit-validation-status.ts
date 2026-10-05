import type {
  TopologyValidationReport,
  UnitValidationStatus,
  ValidationScope,
} from '../types/topology';
import { deriveUnitStatuses } from './validation-report';

export const UNIT_VALIDATION_STATUS_KEY = 'geosix-unit-validation-status';

export interface UnitValidationStatusHandoff {
  generated_at: string;
  scope: ValidationScope;
  target_id: string;
  statuses: Record<string, UnitValidationStatus>;
}

interface HandoffInput {
  report: TopologyValidationReport;
  scope: ValidationScope;
  targetId: string;
  knownUnitIds?: string[];
}

export function buildUnitValidationStatusHandoff({
  report,
  scope,
  targetId,
  knownUnitIds = [],
}: HandoffInput): UnitValidationStatusHandoff {
  return {
    generated_at: new Date().toISOString(),
    scope,
    target_id: targetId,
    statuses: deriveUnitStatuses(report, knownUnitIds),
  };
}

export function publishUnitValidationStatusHandoff(
  handoff: UnitValidationStatusHandoff
): void {
  try {
    sessionStorage.setItem(
      UNIT_VALIDATION_STATUS_KEY,
      JSON.stringify(handoff)
    );
  } catch {
    // Storage may be unavailable (private mode); the 3D view simply reads nothing.
  }
}

export function readUnitValidationStatusHandoff(): UnitValidationStatusHandoff | null {
  try {
    const raw = sessionStorage.getItem(UNIT_VALIDATION_STATUS_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return null;
    const candidate = parsed as Partial<UnitValidationStatusHandoff>;
    if (typeof candidate.target_id !== 'string' || !candidate.statuses) return null;
    return candidate as UnitValidationStatusHandoff;
  } catch {
    return null;
  }
}

export function clearUnitValidationStatusHandoff(): void {
  try {
    sessionStorage.removeItem(UNIT_VALIDATION_STATUS_KEY);
  } catch {
    // Ignore storage failures.
  }
}

import { useCallback, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { PageContainer } from '../../components/layout/PageContainer';
import { ValidationIssueSections } from '../../components/validation/ValidationIssueSections';
import { ValidationSummaryCards } from '../../components/validation/ValidationSummaryCards';
import { ValidationTargetPicker } from '../../components/validation/ValidationTargetPicker';
import { toApiError, type ApiErrorView } from '../../lib/api-error';
import { affectedUnitIds } from '../../lib/validation-report';
import {
  buildUnitValidationStatusHandoff,
  publishUnitValidationStatusHandoff,
} from '../../lib/unit-validation-status';
import { hierarchyService } from '../../services/hierarchy-service';
import { topologyService } from '../../services/topology-service';
import type {
  TopologyValidationReport,
  ValidationScope,
  ValidationTarget,
} from '../../types/topology';

type RunPhase = 'idle' | 'running' | 'success' | 'error';

const ERROR_COPY: Record<
  ApiErrorView['kind'],
  { title: string; guidance: string }
> = {
  not_found: {
    title: 'Target not found',
    guidance: 'The selected building or unit no longer exists. Refresh the hierarchy and try again.',
  },
  unavailable: {
    title: 'Validation API not available',
    guidance:
      'This server does not expose the topology validation API yet. Other modules keep working; run validation again once the backend is upgraded.',
  },
  auth: {
    title: 'Session expired',
    guidance: 'Sign in again to run topology validation.',
  },
  server: {
    title: 'Validation failed on the server',
    guidance: 'The backend reported an error while running the checks. Retry in a moment.',
  },
  network: {
    title: 'Cannot reach the server',
    guidance: 'Check your network connection and retry.',
  },
  unknown: {
    title: 'Validation failed',
    guidance: 'The run could not be completed. Retry or contact support if it persists.',
  },
};

export function TopologyValidationPage() {
  const [scope, setScope] = useState<ValidationScope>('building');
  const [target, setTarget] = useState<ValidationTarget>({});
  const [phase, setPhase] = useState<RunPhase>('idle');
  const [report, setReport] = useState<TopologyValidationReport | null>(null);
  const [error, setError] = useState<ApiErrorView | null>(null);

  const canRun =
    scope === 'building'
      ? Boolean(target.buildingId)
      : Boolean(target.buildingId && target.unitId);

  const handleScopeChange = useCallback((next: ValidationScope) => {
    setScope(next);
    setTarget((current) => ({ buildingId: current.buildingId }));
  }, []);

  const handleTargetChange = useCallback((next: ValidationTarget) => {
    setTarget(next);
  }, []);

  const publishHandoff = async (
    result: TopologyValidationReport,
    activeScope: ValidationScope,
    activeTarget: ValidationTarget
  ) => {
    const targetId =
      activeScope === 'building' ? activeTarget.buildingId : activeTarget.unitId;
    if (!targetId) return;

    let knownUnitIds: string[] = [];
    if (activeScope === 'building' && activeTarget.buildingId) {
      try {
        knownUnitIds = await hierarchyService.listBuildingUnitIds(activeTarget.buildingId);
      } catch {
        knownUnitIds = [];
      }
    } else if (activeTarget.unitId) {
      knownUnitIds = [activeTarget.unitId];
    }

    publishUnitValidationStatusHandoff(
      buildUnitValidationStatusHandoff({
        report: result,
        scope: activeScope,
        targetId,
        knownUnitIds,
      })
    );
  };

  const runValidation = async () => {
    if (!canRun) return;
    setPhase('running');
    setError(null);

    try {
      const result =
        scope === 'building' && target.buildingId
          ? await topologyService.validateBuilding(target.buildingId)
          : await topologyService.validateUnit(target.unitId as string);

      setReport(result);
      setPhase('success');
      void publishHandoff(result, scope, target);
    } catch (raw) {
      setReport(null);
      setError(toApiError(raw));
      setPhase('error');
    }
  };

  const errorCopy = error ? ERROR_COPY[error.kind] : null;
  const affectedCount = report ? affectedUnitIds(report).length : 0;

  return (
    <PageContainer
      title="Topology Validation"
      description="Detect geometry, volumetric overlap, spatial gap, and elevation issues before publishing to the 3D view."
      actions={
        <Button onClick={() => void runValidation()} disabled={!canRun} loading={phase === 'running'}>
          {phase === 'success' ? 'Re-run validation' : 'Run validation'}
        </Button>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <ValidationTargetPicker
          scope={scope}
          target={target}
          onScopeChange={handleScopeChange}
          onTargetChange={handleTargetChange}
        />

        {phase === 'idle' && (
          <EmptyState
            icon="⊡"
            title="No validation run yet"
            description="Select a building or unit above and run validation to inspect geometry, overlap, gap, and elevation findings."
          />
        )}

        {phase === 'running' && (
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <LoadingSpinner size={20} />
              <span style={{ fontSize: '0.875rem' }}>
                Running topology validation…
              </span>
            </div>
          </Card>
        )}

        {phase === 'error' && error && errorCopy && (
          <Card style={{ borderColor: 'var(--danger)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Badge variant={error.kind === 'unavailable' ? 'warning' : 'danger'}>
                  {error.kind === 'unavailable' ? 'Degraded' : 'Error'}
                </Badge>
                <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>
                  {errorCopy.title}
                </span>
              </div>
              <p style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>
                {error.message}
              </p>
              <p style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                {errorCopy.guidance}
              </p>
              <div style={{ marginTop: '0.5rem' }}>
                <Button variant="secondary" onClick={() => void runValidation()}>
                  Retry
                </Button>
              </div>
            </div>
          </Card>
        )}

        {phase === 'success' && report && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <ValidationSummaryCards report={report} affectedUnitCount={affectedCount} />

            {report.summary.valid ? (
              <Card>
                <EmptyState
                  icon="✓"
                  title="All topology checks passed"
                  description="No geometry, overlap, gap, or elevation issues were found for this target. The 3D view status handoff was refreshed."
                />
              </Card>
            ) : (
              <ValidationIssueSections report={report} />
            )}

            <p style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
              Unit status map published to the 3D view handoff: healthy units are marked
              valid, {affectedCount} unit{affectedCount === 1 ? '' : 's'} carry issue
              statuses.
            </p>
          </div>
        )}
      </div>
    </PageContainer>
  );
}

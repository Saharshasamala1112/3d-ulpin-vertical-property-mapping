import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import {
  CATEGORIES,
  CATEGORY_DESCRIPTIONS,
  CATEGORY_LABELS,
  issuesByCategory,
  severityLabel,
} from '../../lib/validation-report';
import type { IssueCategory, TopologyValidationReport } from '../../types/topology';

interface ValidationIssueSectionsProps {
  report: TopologyValidationReport;
}

const severityVariant: Record<string, 'danger' | 'warning' | 'info'> = {
  critical: 'danger',
  error: 'danger',
  warning: 'warning',
};

function initialExpanded(report: TopologyValidationReport): Record<IssueCategory, boolean> {
  const grouped = issuesByCategory(report);
  return {
    geometry: grouped.geometry.length > 0,
    overlap: grouped.overlap.length > 0,
    gap: grouped.gap.length > 0,
    elevation: grouped.elevation.length > 0,
  };
}

export function ValidationIssueSections({ report }: ValidationIssueSectionsProps) {
  const [expanded, setExpanded] = useState<Record<IssueCategory, boolean>>(() =>
    initialExpanded(report)
  );
  const grouped = issuesByCategory(report);

  useEffect(() => {
    setExpanded(initialExpanded(report));
  }, [report]);

  const counts: Record<IssueCategory, number> = {
    geometry: report.summary.geometry_error_count,
    overlap: report.summary.overlap_count,
    gap: report.summary.gap_count,
    elevation: report.summary.elevation_error_count,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {CATEGORIES.map((category) => {
        const issues = grouped[category];
        const isOpen = expanded[category];
        const hasIssues = issues.length > 0;
        return (
          <Card key={category} padding="0">
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={`issues-${category}`}
              onClick={() =>
                setExpanded((current) => ({ ...current, [category]: !current[category] }))
              }
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.75rem',
                padding: '0.875rem 1.25rem',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                color: 'var(--foreground)',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  {isOpen ? '▾' : '▸'}
                </span>
                <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  {CATEGORY_LABELS[category]}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  {CATEGORY_DESCRIPTIONS[category]}
                </span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Badge variant={counts[category] > 0 ? (category === 'overlap' || category === 'geometry' ? 'danger' : 'warning') : 'success'}>
                  {counts[category]}
                </Badge>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  {hasIssues ? `${issues.length} detail${issues.length === 1 ? '' : 's'}` : 'none'}
                </span>
              </span>
            </button>

            {isOpen && (
              <div
                id={`issues-${category}`}
                style={{
                  borderTop: '1px solid var(--border)',
                  padding: '1rem 1.25rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                }}
              >
                {!hasIssues && (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                    No issues in this category.
                  </p>
                )}
                {issues.map((issue) => (
                  <div
                    key={issue.id}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: '6px',
                      padding: '0.75rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        flexWrap: 'wrap',
                      }}
                    >
                      <Badge variant={severityVariant[issue.severity]}>
                        {severityLabel(issue.severity)}
                      </Badge>
                      <code style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                        {issue.code}
                      </code>
                    </div>
                    <p style={{ fontSize: '0.875rem' }}>{issue.message}</p>

                    {issue.unitIds.length > 0 && (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          flexWrap: 'wrap',
                        }}
                      >
                        <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                          Affected units:
                        </span>
                        {issue.unitIds.map((unitId) => (
                          <Link
                            key={unitId}
                            to={`/app/units?unit=${encodeURIComponent(unitId)}`}
                            title={unitId}
                            style={{
                              fontSize: '0.75rem',
                              fontFamily: 'monospace',
                              color: 'var(--primary)',
                              textDecoration: 'none',
                              border: '1px solid var(--border)',
                              borderRadius: '4px',
                              padding: '0.125rem 0.375rem',
                            }}
                          >
                            {unitId.slice(0, 8)}…
                          </Link>
                        ))}
                      </div>
                    )}

                    {issue.details.length > 0 && (
                      <dl
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'max-content 1fr',
                          gap: '0.25rem 0.75rem',
                          margin: 0,
                          fontSize: '0.75rem',
                        }}
                      >
                        {issue.details.map((detail) => (
                          <div key={detail.label} style={{ display: 'contents' }}>
                            <dt style={{ color: 'var(--muted)' }}>{detail.label}:</dt>
                            <dd style={{ margin: 0, fontFamily: 'monospace' }}>
                              {detail.value}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

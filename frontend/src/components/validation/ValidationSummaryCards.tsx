import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { CATEGORY_LABELS } from '../../lib/validation-report';
import type { IssueCategory, TopologyValidationReport } from '../../types/topology';

interface ValidationSummaryCardsProps {
  report: TopologyValidationReport;
  affectedUnitCount: number;
}

interface CountCard {
  category: IssueCategory;
  count: number;
  tone: 'danger' | 'warning' | 'success';
  label: string;
}

const toneVariant: Record<CountCard['tone'], 'danger' | 'warning' | 'success'> = {
  danger: 'danger',
  warning: 'warning',
  success: 'success',
};

export function ValidationSummaryCards({
  report,
  affectedUnitCount,
}: ValidationSummaryCardsProps) {
  const { summary } = report;
  const issueTotal =
    summary.geometry_error_count +
    summary.overlap_count +
    summary.gap_count +
    summary.elevation_error_count;

  const cards: CountCard[] = [
    {
      category: 'geometry',
      count: summary.geometry_error_count,
      tone: summary.geometry_error_count > 0 ? 'danger' : 'success',
      label: CATEGORY_LABELS.geometry,
    },
    {
      category: 'overlap',
      count: summary.overlap_count,
      tone: summary.overlap_count > 0 ? 'danger' : 'success',
      label: CATEGORY_LABELS.overlap,
    },
    {
      category: 'gap',
      count: summary.gap_count,
      tone: summary.gap_count > 0 ? 'warning' : 'success',
      label: CATEGORY_LABELS.gap,
    },
    {
      category: 'elevation',
      count: summary.elevation_error_count,
      tone: summary.elevation_error_count > 0 ? 'warning' : 'success',
      label: CATEGORY_LABELS.elevation,
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Card padding="1.25rem">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Badge variant={summary.valid ? 'success' : 'danger'}>
              {summary.status === 'passed' ? 'Passed' : 'Failed'}
            </Badge>
            <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>
              {summary.valid
                ? 'No issues found'
                : `${issueTotal} issue${issueTotal === 1 ? '' : 's'} found`}
            </span>
          </div>
          <span style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
            {affectedUnitCount} affected unit{affectedUnitCount === 1 ? '' : 's'}
          </span>
        </div>
      </Card>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {cards.map((card) => (
          <Card key={card.category} padding="1rem">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: '0.5rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.8125rem',
                  color: 'var(--muted)',
                  maxWidth: '140px',
                }}
              >
                {card.label}
              </span>
              <span
                style={{
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  lineHeight: 1,
                }}
              >
                {card.count}
              </span>
            </div>
            <div style={{ marginTop: '0.75rem' }}>
              <Badge variant={toneVariant[card.tone]}>
                {card.count === 0 ? 'Clear' : card.tone === 'warning' ? 'Warning' : 'Issues'}
              </Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

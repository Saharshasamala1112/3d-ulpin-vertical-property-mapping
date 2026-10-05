import { Badge } from '../../../components/ui/Badge';
import type { VdcStatus } from './vdc-types';
import { VDC_STATUS_LABELS } from './vdc-validation';

const statusVariants: Record<VdcStatus, 'success' | 'default' | 'warning' | 'danger'> = {
  present: 'success',
  missing: 'default',
  stale: 'warning',
  invalid: 'danger',
};

const statusLabels: Record<VdcStatus, string> = {
  present: 'Present',
  missing: 'Missing',
  stale: 'Stale',
  invalid: 'Invalid',
};

interface VdcStatusBadgeProps {
  status: VdcStatus;
}

/**
 * Renders one of the four backend VDC statuses.
 *
 * The status set is closed on the server, so this is a total lookup; the
 * tooltip explains each state instead of relying on colour alone.
 */
export function VdcStatusBadge({ status }: VdcStatusBadgeProps) {
  return (
    <span title={VDC_STATUS_LABELS[status] ?? status}>
      <Badge variant={statusVariants[status]}>{statusLabels[status] ?? status}</Badge>
    </span>
  );
}

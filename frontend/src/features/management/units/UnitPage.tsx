import { useMemo, useState, lazy, Suspense } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageContainer } from '../../../components/layout/PageContainer';
import { Button } from '../../../components/ui/Button';
import { Badge } from '../../../components/ui/Badge';
import { Card } from '../../../components/ui/Card';
import { DataTable, type DataTableColumn } from '../../../components/ui/DataTable';
import { Dialog } from '../../../components/ui/Dialog';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { Alert } from '../../../components/ui/Alert';
import { ErrorBanner } from '../shared/ErrorBanner';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { useResourceList } from '../shared/useResourceList';
import { useManagementPermissions } from '../shared/permissions';
import { archiveUnit, listUnits } from './unit-service';
import { UNIT_STATUSES } from './unit-validation';
import type { Unit } from './unit-types';
import { VdcStatusBadge } from '../vdc/VdcStatusBadge';
import { toApiError, type ApiError } from '../../../services/api-error';
const UnitFormDialog = lazy(() => import('./UnitFormDialog'));
const UnitVdcPanel = lazy(() => import('./UnitVdcPanel'));

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'active':
      return 'success';
    case 'sold':
      return 'info';
    case 'leased':
      return 'info';
    case 'planned':
      return 'warning';
    case 'archived':
      return 'default';
    default:
      return 'default';
  }
}

export function UnitPage() {
  const { floorId = null } = useParams<{ floorId: string }>();
  const navigate = useNavigate();
  const permissions = useManagementPermissions();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Unit | null>(null);
  const [archiving, setArchiving] = useState<Unit | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [vdcUnit, setVdcUnit] = useState<Unit | null>(null);
  /** Bumped to force the open VDC panel to re-read after a list change. */
  const [vdcRevision, setVdcRevision] = useState(0);

  const { data, loading, error, reload } = useResourceList<Unit[]>(
    () => listUnits(floorId as string),
    `floor=${floorId}`,
    Boolean(floorId)
  );

  const rows = useMemo(() => data ?? [], [data]);

  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (!term) return true;
      return (
        row.unit_identifier.toLowerCase().includes(term) ||
        row.unit_type.toLowerCase().includes(term) ||
        (row.vdc_code ?? '').toLowerCase().includes(term)
      );
    });
  }, [rows, search, statusFilter]);

  const columns: DataTableColumn<Unit>[] = [
    {
      key: 'identifier',
      header: 'Identifier',
      render: (row) => (
        <Link to={`/app/vdc`} style={{ color: 'var(--primary)' }} title="Open the VDC workspace">
          {row.unit_identifier}
        </Link>
      ),
    },
    { key: 'type', header: 'Type', render: (row) => row.unit_type },
    { key: 'area', header: 'Area (sqm)', align: 'right', render: (row) => row.area_sqm },
    {
      key: 'bbox',
      header: 'Bounding box (m)',
      render: (row) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
          x {row.x_min}–{row.x_max} · y {row.y_min}–{row.y_max} · z {row.z_min}–{row.z_max}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <Badge variant={statusVariant(row.status)}>{row.status}</Badge>,
    },
    {
      key: 'vdc',
      header: 'VDC code',
      render: (row) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
          {row.vdc_code ?? <span style={{ color: 'var(--muted)' }}>—</span>}
          <VdcStatusBadge status={row.vdc_status} />
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (row) => (
        <div style={{ display: 'flex', gap: '0.375rem', justifyContent: 'flex-end' }}>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setNotice(null);
              setVdcRevision((value) => value + 1);
              setVdcUnit(row);
            }}
          >
            VDC
          </Button>
          {permissions.can('edit') && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setEditing(row);
                setFormOpen(true);
              }}
            >
              Edit
            </Button>
          )}
          {permissions.can('delete') && row.status !== 'archived' && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setArchiveError(null);
                setArchiving(row);
              }}
            >
              Archive
            </Button>
          )}
        </div>
      ),
    },
  ];

  const handleArchive = async () => {
    if (!archiving) return;
    setArchiveBusy(true);
    setArchiveError(null);
    try {
      await archiveUnit(archiving.id);
      setNotice(`${archiving.unit_identifier} was archived. The record is kept.`);
      setArchiving(null);
      reload();
    } catch (failure) {
      setArchiveError(toApiError(failure));
    } finally {
      setArchiveBusy(false);
    }
  };

  if (!floorId) {
    return (
      <PageContainer title="Units">
        <Card>
          <EmptyState
            title="No floor selected"
            description="Units belong to a floor. Open a floor to see and manage its units."
            action={<Button onClick={() => navigate('/app/floors')}>Go to floors</Button>}
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Units"
      description="Units in the selected floor. Archiving keeps the record and sets its status to archived."
      actions={
        permissions.can('create') ? (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            New unit
          </Button>
        ) : null
      }
    >
      <Card>
        <div
          style={{
            display: 'flex',
            gap: '0.75rem',
            flexWrap: 'wrap',
            alignItems: 'flex-end',
            marginBottom: '1rem',
          }}
        >
          <div style={{ flex: '1 1 240px' }}>
            <label
              htmlFor="unit-search"
              style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '0.375rem' }}
            >
              Search
            </label>
            <input
              id="unit-search"
              value={search}
              placeholder="Identifier, type or VDC code"
              onChange={(event) => setSearch(event.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--input-border)',
                background: 'var(--input-bg)',
                color: 'var(--foreground)',
                fontSize: '0.875rem',
              }}
            />
          </div>
          <div>
            <label
              htmlFor="unit-status"
              style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '0.375rem' }}
            >
              Status
            </label>
            <select
              id="unit-status"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              style={{
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--input-border)',
                background: 'var(--input-bg)',
                color: 'var(--foreground)',
                fontSize: '0.875rem',
              }}
            >
              <option value="">All statuses</option>
              {[...UNIT_STATUSES].map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {notice && (
          <div style={{ marginBottom: '1rem' }}>
            <Alert variant="success" onDismiss={() => setNotice(null)}>
              {notice}
            </Alert>
          </div>
        )}

        {error && (
          <div style={{ marginBottom: '1rem' }}>
            <ErrorBanner error={error} onDismiss={reload} />
          </div>
        )}

        {loading ? (
          <LoadingSpinner />
        ) : error && rows.length === 0 ? null : rows.length === 0 ? (
          <EmptyState title="No units on this floor" description="Create the first unit for this floor." />
        ) : (
          <DataTable
            columns={columns}
            rows={visibleRows}
            rowKey={(row) => row.id}
            emptyMessage="No units match your search."
          />
        )}
      </Card>

      {vdcUnit && (
        <Dialog
          open
          onClose={() => setVdcUnit(null)}
          title={`VDC for ${vdcUnit.unit_identifier}`}
          maxWidth="560px"
        >
          <Suspense fallback={<LoadingSpinner size={20} />}>
            <UnitVdcPanel
              unitId={vdcUnit.id}
              revision={vdcRevision}
              canEdit={permissions.can('edit')}
              onChanged={() => {
                // The stored code and its status both changed, so refresh the list.
                reload();
              }}
            />
          </Suspense>
        </Dialog>
      )}

      {formOpen && (
        <Suspense fallback={null}>
        <UnitFormDialog
          open={formOpen}
          unit={editing}
          floorId={floorId}
          onClose={() => setFormOpen(false)}
          onSaved={(unit, mode) => {
            setNotice(
              mode === 'create'
                ? `Unit ${unit.unit_identifier} created.`
                : `Unit ${unit.unit_identifier} updated.`
            );
            reload();
          }}
        />
        </Suspense>
      )}

      {archiving && (
        <ConfirmDialog
          open
          title="Archive unit"
          message={`Set the status of "${archiving.unit_identifier}" to archived?`}
          confirmLabel="Archive unit"
          busy={archiveBusy}
          onCancel={() => setArchiving(null)}
          onConfirm={handleArchive}
        >
          {archiveError ? (
            <Alert variant="error" title="Could not archive unit">
              {archiveError.displayMessage}
            </Alert>
          ) : (
            <Alert variant="warning" title="This is an archive, not a deletion">
              The unit record is kept and stays in this list with status <strong>archived</strong>. The
              API offers no way to restore it from this screen; use Edit to change the status back.
            </Alert>
          )}
        </ConfirmDialog>
      )}
    </PageContainer>
  );
}

export default UnitPage;

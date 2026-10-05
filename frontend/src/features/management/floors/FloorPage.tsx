import { useCallback, useMemo, useState, lazy, Suspense } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageContainer } from '../../../components/layout/PageContainer';
import { Button } from '../../../components/ui/Button';
import { Badge } from '../../../components/ui/Badge';
import { Card } from '../../../components/ui/Card';
import { DataTable, type DataTableColumn } from '../../../components/ui/DataTable';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { Alert } from '../../../components/ui/Alert';
import { ErrorBanner } from '../shared/ErrorBanner';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { useResourceList } from '../shared/useResourceList';
import { useManagementPermissions } from '../shared/permissions';
import { deleteFloor, listFloors } from './floor-service';
import { listUnits } from '../units/unit-service';
import type { Floor } from './floor-types';
import { toApiError, type ApiError } from '../../../services/api-error';
const FloorFormDialog = lazy(() => import('./FloorFormDialog'));

export function FloorPage() {
  const { buildingId = null } = useParams<{ buildingId: string }>();
  const navigate = useNavigate();
  const permissions = useManagementPermissions();

  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Floor | null>(null);
  const [deleting, setDeleting] = useState<Floor | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  /**
   * Unit counts are DERIVED, not provided.
   *
   * No endpoint returns a unit count for a floor, so counting costs one extra
   * request per floor (`GET /api/v1/floors/{id}/units`). Opt-in for the same
   * reason as buildings: avoid an N+1 request storm on every page load.
   */
  const [showUnitCounts, setShowUnitCounts] = useState(false);
  const [unitCounts, setUnitCounts] = useState<Record<string, number>>({});
  const [countsLoading, setCountsLoading] = useState(false);

  const { data, loading, error, reload } = useResourceList<Floor[]>(
    () => listFloors(buildingId as string),
    `building=${buildingId}`,
    Boolean(buildingId)
  );

  const rows = useMemo(() => data ?? [], [data]);

  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(
      (row) =>
        String(row.floor_number).includes(term) ||
        (row.level_name ?? '').toLowerCase().includes(term) ||
        row.floor_type.toLowerCase().includes(term)
    );
  }, [rows, search]);

  const loadUnitCounts = useCallback(async () => {
    setCountsLoading(true);
    const entries = await Promise.all(
      rows.map(async (row) => {
        try {
          const units = await listUnits(row.id);
          return [row.id, units.length] as const;
        } catch {
          return [row.id, -1] as const;
        }
      })
    );
    setUnitCounts(Object.fromEntries(entries));
    setCountsLoading(false);
  }, [rows]);

  const toggleUnitCounts = () => {
    const next = !showUnitCounts;
    setShowUnitCounts(next);
    if (next && Object.keys(unitCounts).length === 0) {
      void loadUnitCounts();
    }
  };

  const columns: DataTableColumn<Floor>[] = [
    {
      key: 'number',
      header: 'Floor',
      render: (row) => (
        <Link to={`/app/units/${encodeURIComponent(row.id)}`} style={{ color: 'var(--primary)' }}>
          {row.level_name ? `${row.level_name} (${row.floor_number})` : row.floor_number}
        </Link>
      ),
    },
    { key: 'type', header: 'Type', render: (row) => <Badge>{row.floor_type}</Badge> },
    {
      key: 'elevation',
      header: 'Elevation (m)',
      align: 'right',
      render: (row) => `${row.elevation_min} – ${row.elevation_max}`,
    },
    ...(showUnitCounts
      ? [
          {
            key: 'units',
            header: 'Units',
            align: 'right' as const,
            render: (row: Floor) => {
              const count = unitCounts[row.id];
              if (count === undefined) return '—';
              if (count === -1) return <span title="Could not load units">n/a</span>;
              return count;
            },
          },
        ]
      : []),
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (row) => (
        <div style={{ display: 'flex', gap: '0.375rem', justifyContent: 'flex-end' }}>
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
          {permissions.can('delete') && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setDeleteError(null);
                setDeleting(row);
              }}
            >
              Delete
            </Button>
          )}
        </div>
      ),
    },
  ];

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteFloor(deleting.id);
      setNotice(`Floor ${deleting.floor_number} was deleted.`);
      setDeleting(null);
      reload();
    } catch (failure) {
      setDeleteError(toApiError(failure));
    } finally {
      setDeleteBusy(false);
    }
  };

  if (!buildingId) {
    return (
      <PageContainer title="Floors">
        <Card>
          <EmptyState
            title="No building selected"
            description="Floors belong to a building. Open a building to see and manage its floors."
            action={<Button onClick={() => navigate('/app/buildings')}>Go to buildings</Button>}
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Floors"
      description="Floors in the selected building. Deleting a floor permanently removes its units."
      actions={
        permissions.can('create') ? (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            New floor
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
              htmlFor="floor-search"
              style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '0.375rem' }}
            >
              Search
            </label>
            <input
              id="floor-search"
              value={search}
              placeholder="Floor number, level name or type"
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
          <Button variant="secondary" onClick={toggleUnitCounts} loading={countsLoading}>
            {showUnitCounts ? 'Hide unit counts' : 'Show unit counts'}
          </Button>
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
          <EmptyState
            title="No floors in this building"
            description="Create the first floor to add units."
          />
        ) : (
          <DataTable
            columns={columns}
            rows={visibleRows}
            rowKey={(row) => row.id}
            emptyMessage="No floors match your search."
          />
        )}
      </Card>

      {formOpen && (
        <Suspense fallback={null}>
        <FloorFormDialog
          open={formOpen}
          floor={editing}
          buildingId={buildingId}
          onClose={() => setFormOpen(false)}
          onSaved={(floor, mode) => {
            setNotice(
              mode === 'create' ? `Floor ${floor.floor_number} created.` : `Floor ${floor.floor_number} updated.`
            );
            reload();
          }}
        />
        </Suspense>
      )}

      {deleting && (
        <ConfirmDialog
          open
          title="Delete floor"
          message={`Permanently delete floor ${deleting.floor_number}? This cannot be undone.`}
          confirmLabel="Delete floor"
          busy={deleteBusy}
          onCancel={() => setDeleting(null)}
          onConfirm={handleDelete}
        >
          {deleteError ? (
            <Alert variant="error" title="Could not delete floor">
              {deleteError.displayMessage}
            </Alert>
          ) : (
            <Alert variant="warning" title="This also deletes its units">
              Every unit on this floor is removed with it. The API applies this in one transaction and
              provides no undo.
            </Alert>
          )}
        </ConfirmDialog>
      )}
    </PageContainer>
  );
}

export default FloorPage;

import { useCallback, useMemo, useState, lazy, Suspense } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
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
import { deleteBuilding, listBuildings } from './building-service';
import { listFloors } from '../floors/floor-service';
import type { Building } from './building-types';
import { toApiError, type ApiError } from '../../../services/api-error';
const BuildingFormDialog = lazy(() => import('./BuildingFormDialog'));

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'under_construction':
      return 'info';
    case 'planned':
      return 'warning';
    case 'demolished':
      return 'danger';
    default:
      return 'default';
  }
}

export function BuildingPage() {
  const { parcelId = null } = useParams<{ parcelId: string }>();
  const navigate = useNavigate();
  const permissions = useManagementPermissions();

  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Building | null>(null);
  const [deleting, setDeleting] = useState<Building | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  /**
   * Floor counts are DERIVED, not provided.
   *
   * The buildings API has no aggregate, so counting requires one extra request
   * per building (`GET /api/v1/buildings/{id}/floors`). That is opt-in to
   * avoid an N+1 request storm on every page load; the column only renders
   * once the user asks for it.
   */
  const [showFloorCounts, setShowFloorCounts] = useState(false);
  const [floorCounts, setFloorCounts] = useState<Record<string, number>>({});
  const [countsLoading, setCountsLoading] = useState(false);

  const { data, loading, error, reload } = useResourceList<Building[]>(
    () => listBuildings(parcelId as string),
    `parcel=${parcelId}`,
    Boolean(parcelId)
  );

  const rows = useMemo(() => data ?? [], [data]);

  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(
      (row) =>
        row.building_identifier.toLowerCase().includes(term) ||
        (row.name ?? '').toLowerCase().includes(term) ||
        row.building_type.toLowerCase().includes(term) ||
        row.construction_status.toLowerCase().includes(term)
    );
  }, [rows, search]);

  const loadFloorCounts = useCallback(async () => {
    setCountsLoading(true);
    const entries = await Promise.all(
      rows.map(async (row) => {
        try {
          const floors = await listFloors(row.id);
          return [row.id, floors.length] as const;
        } catch {
          // A failed count must not break the list; show it as unknown.
          return [row.id, -1] as const;
        }
      })
    );
    setFloorCounts(Object.fromEntries(entries));
    setCountsLoading(false);
  }, [rows]);

  const toggleFloorCounts = () => {
    const next = !showFloorCounts;
    setShowFloorCounts(next);
    if (next && Object.keys(floorCounts).length === 0) {
      void loadFloorCounts();
    }
  };

  const columns: DataTableColumn<Building>[] = [
    {
      key: 'identifier',
      header: 'Identifier',
      render: (row) => (
        <Link to={`/app/floors/${encodeURIComponent(row.id)}`} style={{ color: 'var(--primary)' }}>
          {row.building_identifier}
        </Link>
      ),
    },
    { key: 'name', header: 'Name', render: (row) => row.name ?? <span style={{ color: 'var(--muted)' }}>—</span> },
    { key: 'type', header: 'Type', render: (row) => row.building_type },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <Badge variant={statusVariant(row.construction_status)}>{row.construction_status}</Badge>,
    },
    ...(showFloorCounts
      ? [
          {
            key: 'floors',
            header: 'Floors',
            align: 'right' as const,
            render: (row: Building) => {
              const count = floorCounts[row.id];
              if (count === undefined) return '—';
              if (count === -1) return <span title="Could not load floors">n/a</span>;
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
      await deleteBuilding(deleting.id);
      setNotice(`${deleting.building_identifier} was deleted.`);
      setDeleting(null);
      reload();
    } catch (failure) {
      setDeleteError(toApiError(failure));
    } finally {
      setDeleteBusy(false);
    }
  };

  if (!parcelId) {
    return (
      <PageContainer title="Buildings">
        <Card>
          <EmptyState
            title="No parcel selected"
            description="Buildings belong to a parcel. Open a parcel to see and manage its buildings."
            action={<Button onClick={() => navigate('/app/parcels')}>Go to parcels</Button>}
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Buildings"
      description="Buildings on the selected parcel. Deleting a building permanently removes its floors and units."
      actions={
        permissions.can('create') ? (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            New building
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
              htmlFor="building-search"
              style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '0.375rem' }}
            >
              Search
            </label>
            <input
              id="building-search"
              value={search}
              placeholder="Identifier, name, type or status"
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
          <Button variant="secondary" onClick={toggleFloorCounts} loading={countsLoading}>
            {showFloorCounts ? 'Hide floor counts' : 'Show floor counts'}
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
            title="No buildings on this parcel"
            description="Create the first building to add floors and units."
          />
        ) : (
          <DataTable
            columns={columns}
            rows={visibleRows}
            rowKey={(row) => row.id}
            emptyMessage="No buildings match your search."
          />
        )}
      </Card>

      {formOpen && (
        <Suspense fallback={null}>
        <BuildingFormDialog
          open={formOpen}
          building={editing}
          parcelId={parcelId}
          onClose={() => setFormOpen(false)}
          onSaved={(building, mode) => {
            setNotice(
              mode === 'create'
                ? `Building ${building.building_identifier} created.`
                : `Building ${building.building_identifier} updated.`
            );
            reload();
          }}
        />
        </Suspense>
      )}

      {deleting && (
        <ConfirmDialog
          open
          title="Delete building"
          message={`Permanently delete "${deleting.building_identifier}"? This cannot be undone.`}
          confirmLabel="Delete building"
          busy={deleteBusy}
          onCancel={() => setDeleting(null)}
          onConfirm={handleDelete}
        >
          {deleteError ? (
            <Alert variant="error" title="Could not delete building">
              {deleteError.displayMessage}
            </Alert>
          ) : (
            <Alert variant="warning" title="This also deletes its floors and units">
              Every floor of this building is removed, and every unit on those floors is removed with
              them. The API applies this in one transaction and provides no undo.
            </Alert>
          )}
        </ConfirmDialog>
      )}
    </PageContainer>
  );
}

export default BuildingPage;

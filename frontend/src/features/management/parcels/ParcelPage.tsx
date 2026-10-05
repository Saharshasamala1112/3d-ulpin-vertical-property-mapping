import { useMemo, useState, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageContainer } from '../../../components/layout/PageContainer';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { Badge } from '../../../components/ui/Badge';
import { Card } from '../../../components/ui/Card';
import { DataTable, type DataTableColumn } from '../../../components/ui/DataTable';
import { Pagination } from '../../../components/ui/Pagination';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { Alert } from '../../../components/ui/Alert';
import { ErrorBanner } from '../shared/ErrorBanner';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { GeoJSONImportPanel } from '../shared/GeoJSONImportPanel';
import { useResourceList } from '../shared/useResourceList';
import { useManagementPermissions } from '../shared/permissions';
import { archiveParcel, listParcels } from './parcel-service';
import { PARCEL_STATUSES, type GeoJSONFeature } from './parcel-types';
import { toApiError, type ApiError } from '../../../services/api-error';
const ParcelFormDialog = lazy(() => import('./ParcelFormDialog'));

const DEFAULT_PER_PAGE = 20;

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'active':
      return 'success';
    case 'registered':
      return 'info';
    case 'draft':
      return 'warning';
    case 'archived':
      return 'default';
    default:
      return 'default';
  }
}

export function ParcelPage() {
  const navigate = useNavigate();
  const permissions = useManagementPermissions();

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [search, setSearch] = useState('');

  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<GeoJSONFeature | null>(null);
  const [archiving, setArchiving] = useState<GeoJSONFeature | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data, loading, error, reload } = useResourceList(
    () => listParcels({ page, perPage, status: statusFilter || null }),
    `page=${page}&perPage=${perPage}&status=${statusFilter}`
  );

  const rows = useMemo(() => data?.data ?? [], [data]);

  /**
   * Client-side search over the CURRENT PAGE only.
   *
   * The parcels endpoint has no text-search parameter (it supports page,
   * per_page, status and a lon/lat bbox), so searching is intentionally scoped
   * to the loaded page rather than pretending to be a server-side search.
   */
  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((row) => {
      const properties = row.properties;
      return (
        properties.parcel_identifier.toLowerCase().includes(term) ||
        properties.ulpin.toLowerCase().includes(term) ||
        properties.status.toLowerCase().includes(term)
      );
    });
  }, [rows, search]);

  const columns: DataTableColumn<GeoJSONFeature>[] = [
    {
      key: 'identifier',
      header: 'Identifier',
      render: (row) => row.properties.parcel_identifier,
    },
    { key: 'ulpin', header: 'ULPIN', render: (row) => row.properties.ulpin },
    {
      key: 'area',
      header: 'Area (sqm)',
      align: 'right',
      render: (row) => row.properties.area_sqm.toLocaleString(),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <Badge variant={statusVariant(row.properties.status)}>{row.properties.status}</Badge>,
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
            onClick={() => navigate(`/app/buildings/${encodeURIComponent(row.id)}`)}
          >
            Buildings
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
          {permissions.can('archive') && row.properties.status !== 'archived' && (
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
      await archiveParcel(archiving.id);
      setNotice(`${archiving.properties.parcel_identifier} was archived.`);
      setArchiving(null);
      reload();
    } catch (failure) {
      setArchiveError(toApiError(failure));
    } finally {
      setArchiveBusy(false);
    }
  };

  return (
    <PageContainer
      title="Parcels"
      description="Cadastral parcels. Deleting a parcel archives it; it is not removed."
      actions={
        permissions.can('create') || permissions.can('import') ? (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {permissions.can('import') && (
            <Button variant="secondary" onClick={() => setImportOpen((open) => !open)}>
              {importOpen ? 'Close import' : 'Import GeoJSON'}
            </Button>
          )}
          {permissions.can('create') && (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            New parcel
          </Button>
          )}
          </div>
        ) : null
      }
    >
      {importOpen && permissions.can('import') && (
        <GeoJSONImportPanel
          onClose={() => setImportOpen(false)}
          onImported={() => {
            setNotice('GeoJSON import finished. The parcel list has been refreshed.');
            reload();
          }}
        />
      )}
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
            <Input
              label="Search this page"
              value={search}
              placeholder="Identifier, ULPIN or status"
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div style={{ flex: '0 1 200px' }}>
            <Select
              label="Status"
              placeholder="All statuses"
              value={statusFilter}
              options={[...PARCEL_STATUSES]}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
            />
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
          <EmptyState
            title="No parcels yet"
            description="Create the first parcel to start mapping buildings, floors and units."
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={visibleRows}
              rowKey={(row) => row.id}
              emptyMessage="No parcels on this page match your search."
            />
            <Pagination
              page={page}
              perPage={perPage}
              total={data?.meta.total ?? 0}
              totalPages={data?.meta.total_pages ?? 1}
              onPageChange={setPage}
              onPerPageChange={(value) => {
                setPerPage(value);
                setPage(1);
              }}
              itemLabel="parcels"
            />
          </>
        )}
      </Card>

      {formOpen && (
        <Suspense fallback={null}>
        <ParcelFormDialog
          open={formOpen}
          parcel={editing}
          onClose={() => setFormOpen(false)}
          onSaved={(parcel, mode) => {
            setNotice(
              mode === 'create'
                ? `Parcel ${parcel.properties.parcel_identifier} created.`
                : `Parcel ${parcel.properties.parcel_identifier} updated.`
            );
            reload();
          }}
        />
        </Suspense>
      )}

      {archiving && (
        <ConfirmDialog
          open
          destructive={false}
          title="Archive parcel"
          message={`Set the status of "${archiving.properties.parcel_identifier}" to archived? The record is kept and stays in this list.`}
          confirmLabel="Archive"
          busy={archiveBusy}
          onCancel={() => setArchiving(null)}
          onConfirm={handleArchive}
        >
          {archiveError ? (
            <Alert variant="error" title="Could not archive parcel">
              {archiveError.displayMessage}
            </Alert>
          ) : (
            <p style={{ fontSize: '0.8125rem', color: 'var(--muted)', margin: 0 }}>
              The parcel stays in this list with status <strong>archived</strong>. Use the status
              filter to hide it, or Edit to change the status back. Buildings linked to this parcel
              are not affected.
            </p>
          )}
        </ConfirmDialog>
      )}
    </PageContainer>
  );
}

export default ParcelPage;

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { fireEvent } from '@testing-library/react';
import { ParcelPage } from './ParcelPage';
import { ApiError } from '../../../services/api-error';
import type { GeoJSONFeature, ParcelListResponse } from './parcel-types';
import type { GeoJSONImportReport } from '../shared/geojson-import';

vi.mock('./parcel-service', () => ({
  listParcels: vi.fn(),
  archiveParcel: vi.fn(),
  importBuildingsGeoJSON: vi.fn(),
  importParcelsGeoJSON: vi.fn(),
}));

vi.mock('../../../app/AuthContext', () => ({
  useAuth: vi.fn(),
}));

import {
  archiveParcel,
  importBuildingsGeoJSON,
  importParcelsGeoJSON,
  listParcels,
} from './parcel-service';
import { useAuth } from '../../../app/AuthContext';

const mockList = vi.mocked(listParcels);
const mockArchive = vi.mocked(archiveParcel);
const mockImportBuildings = vi.mocked(importBuildingsGeoJSON);
const mockImportParcels = vi.mocked(importParcelsGeoJSON);

function feature(overrides: Partial<GeoJSONFeature['properties']> & { id?: string } = {}): GeoJSONFeature {
  const id = overrides.id ?? 'parcel-1';
  return {
    type: 'Feature',
    id,
    geometry: { type: 'MultiPolygon', coordinates: [] },
    properties: {
      id,
      parcel_identifier: 'SEC-1',
      ulpin: 'ULPIN-1',
      area_sqm: 100,
      status: 'draft',
      metadata: null,
      ...overrides,
    },
  };
}

function listResponse(rows: GeoJSONFeature[], overrides: Partial<ParcelListResponse['meta']> = {}): ParcelListResponse {
  return {
    data: rows,
    meta: { page: 1, per_page: 20, total: rows.length, total_pages: 1, ...overrides },
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/app/parcels']}>
      <ParcelPage />
    </MemoryRouter>
  );
}

describe('ParcelPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'admin',
        email: 'admin@example.com',
        full_name: 'Admin',
        role: 'admin',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
  });

  it('renders one row per parcel returned by the API', async () => {
    mockList.mockResolvedValueOnce(
      listResponse([
        feature({ id: 'p1', parcel_identifier: 'SEC-1', ulpin: 'ULPIN-1' }),
        feature({ id: 'p2', parcel_identifier: 'SEC-2', ulpin: 'ULPIN-2' }),
      ])
    );

    renderPage();

    expect(await screen.findByText('SEC-1')).toBeInTheDocument();
    expect(screen.getByText('SEC-2')).toBeInTheDocument();
    expect(screen.getByText('ULPIN-1')).toBeInTheDocument();
  });

  it('requests the default first page with no status filter', async () => {
    mockList.mockResolvedValueOnce(listResponse([]));

    renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalledWith({ page: 1, perPage: 20, status: null }));
  });

  it('filters the current page by identifier, ULPIN or status', async () => {
    mockList.mockResolvedValueOnce(
      listResponse([
        feature({ id: 'p1', parcel_identifier: 'SEC-1', ulpin: 'ULPIN-1', status: 'draft' }),
        feature({ id: 'p2', parcel_identifier: 'SEC-2', ulpin: 'ZZZ-9', status: 'active' }),
      ])
    );

    renderPage();
    await screen.findByText('SEC-1');

    fireEvent.change(screen.getByLabelText('Search this page'), { target: { value: 'ZZZ' } });

    expect(screen.queryByText('SEC-1')).not.toBeInTheDocument();
    expect(screen.getByText('SEC-2')).toBeInTheDocument();
  });

  it('shows a page-scoped empty message when the search matches nothing', async () => {
    mockList.mockResolvedValueOnce(listResponse([feature({ parcel_identifier: 'SEC-1' })]));

    renderPage();
    await screen.findByText('SEC-1');

    fireEvent.change(screen.getByLabelText('Search this page'), { target: { value: 'nope' } });

    expect(
      screen.getByText('No parcels on this page match your search.')
    ).toBeInTheDocument();
  });

  it('previews a parcel FeatureCollection before enabling the explicit import action', async () => {
    mockList.mockResolvedValue(listResponse([]));
    const preview: GeoJSONImportReport = {
      dry_run: true,
      created: 1,
      updated: 0,
      skipped: 0,
      failed: 1,
      features: [
        { index: 1, status: 'created', key: 'GEOSX00001', record_id: null, reason: null },
        { index: 2, status: 'failed', key: 'bad', record_id: null, reason: 'Invalid ULPIN.' },
      ],
    };
    mockImportParcels
      .mockResolvedValueOnce(preview)
      .mockResolvedValueOnce({ ...preview, dry_run: false, created: 1 });

    renderPage();
    await screen.findByText('No parcels yet');
    fireEvent.click(screen.getByRole('button', { name: 'Import GeoJSON' }));

    const fileContents = JSON.stringify({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { ulpin: 'GEOSX00001' }, geometry: null }],
    });
    const file = new File([fileContents], 'parcels.geojson', { type: 'application/geo+json' });
    Object.defineProperty(file, 'text', { value: () => Promise.resolve(fileContents) });
    fireEvent.change(screen.getByLabelText('GeoJSON file'), { target: { files: [file] } });
    expect(await screen.findByText('Selected: parcels.geojson')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Preview import' }));

    expect(await screen.findByText(/Preview only — no data was written/i)).toBeInTheDocument();
    expect(screen.getByText('Invalid ULPIN.')).toBeInTheDocument();
    expect(mockImportParcels).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ type: 'FeatureCollection' }),
      { dryRun: true, ulpinProperty: 'ulpin' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm and import valid features' }));
    expect(await screen.findByText(/Import complete/i)).toBeInTheDocument();
    expect(mockImportParcels).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ type: 'FeatureCollection' }),
      { dryRun: false, ulpinProperty: 'ulpin' }
    );
  });

  it('does not expose import controls to a reader', async () => {
    mockList.mockResolvedValueOnce(listResponse([]));
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'reader',
        email: 'reader@example.com',
        full_name: 'Reader',
        role: 'reader',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    renderPage();
    await screen.findByText('No parcels yet');

    expect(screen.queryByRole('button', { name: 'Import GeoJSON' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New parcel' })).not.toBeInTheDocument();
  });

  it('routes building previews with the default parcel id', async () => {
    mockList.mockResolvedValue(listResponse([]));
    mockImportBuildings.mockResolvedValueOnce({
      dry_run: true,
      created: 1,
      updated: 0,
      skipped: 0,
      failed: 0,
      features: [
        { index: 1, status: 'created', key: 'BLDG-1', record_id: null, reason: null },
      ],
    });

    renderPage();
    await screen.findByText('No parcels yet');
    fireEvent.click(screen.getByRole('button', { name: 'Import GeoJSON' }));
    fireEvent.change(screen.getByLabelText('Data to import'), {
      target: { value: 'buildings' },
    });
    fireEvent.change(screen.getByLabelText('Default parcel ID (optional)'), {
      target: { value: 'parcel-uuid' },
    });

    const fileContents = JSON.stringify({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { building_identifier: 'BLDG-1' }, geometry: null }],
    });
    const file = new File([fileContents], 'buildings.geojson');
    Object.defineProperty(file, 'text', { value: () => Promise.resolve(fileContents) });
    fireEvent.change(screen.getByLabelText('GeoJSON file'), { target: { files: [file] } });
    expect(await screen.findByText('Selected: buildings.geojson')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Preview import' }));

    await screen.findByText(/Preview only — no data was written/i);
    expect(mockImportBuildings).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'FeatureCollection' }),
      { dryRun: true, parcelId: 'parcel-uuid' }
    );
  });

  it('distinguishes "no parcels at all" from "no search matches"', async () => {
    mockList.mockResolvedValueOnce(listResponse([]));

    renderPage();

    expect(await screen.findByText('No parcels yet')).toBeInTheDocument();
  });

  it('sends the selected status to the API and resets to page 1', async () => {
    mockList.mockResolvedValue(listResponse([]));

    renderPage();
    await screen.findByText('No parcels yet');

    mockList.mockClear();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'archived' } });

    await waitFor(() =>
      expect(mockList).toHaveBeenCalledWith({ page: 1, perPage: 20, status: 'archived' })
    );
  });

  it('surfaces a list failure through the error banner', async () => {
    mockList.mockRejectedValueOnce(
      new ApiError({ status: 500, errorCode: 'INTERNAL_ERROR', message: 'Internal server error' })
    );

    renderPage();

    expect(await screen.findByTestId('error-banner-message')).toHaveTextContent(
      /server could not process the request/i
    );
  });

  describe('archiving', () => {
    it('words the action as "Archive" and does not claim the row is hidden', async () => {
      mockList.mockResolvedValueOnce(listResponse([feature({ status: 'draft' })]));

      renderPage();
      await screen.findByText('SEC-1');

      fireEvent.click(screen.getByRole('button', { name: 'Archive' }));

      const dialog = await screen.findByRole('dialog');
      // The backend only flips `status` to archived, so the unfiltered list
      // still renders the row. The copy must not say otherwise.
      expect(dialog).toHaveTextContent(/The record is kept and stays in this list/i);
      expect(within(dialog).queryByText(/hidden from active views/i)).not.toBeInTheDocument();
      expect(dialog).toHaveTextContent(/Buildings linked to this parcel are not affected/i);
    });

    it('calls archiveParcel and reports success, then reloads the list', async () => {
      mockList.mockResolvedValueOnce(listResponse([feature({ id: 'p1', status: 'draft' })]));
      mockArchive.mockResolvedValueOnce(undefined);

      renderPage();
      await screen.findByText('SEC-1');

      fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Archive' }));

      expect(await screen.findByText(/SEC-1 was archived\./)).toBeInTheDocument();
      expect(mockArchive).toHaveBeenCalledWith('p1');
      // A successful archive returns 204 with no body and must not break the UI.
      await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
    });

    it('keeps the confirmation open and shows the message when archiving fails', async () => {
      mockList.mockResolvedValue(listResponse([feature({ id: 'p1', status: 'draft' })]));
      mockArchive.mockRejectedValueOnce(
        new ApiError({ status: 409, errorCode: 'CONFLICT', message: 'Parcel is referenced' })
      );

      renderPage();
      await screen.findByText('SEC-1');

      fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Archive' }));

      expect(await within(dialog).findByText('Parcel is referenced')).toBeInTheDocument();
    });

    it('does not offer Archive for an already-archived parcel', async () => {
      mockList.mockResolvedValueOnce(listResponse([feature({ id: 'p1', status: 'archived' })]));

      renderPage();
      await screen.findByText('SEC-1');

      expect(screen.queryByRole('button', { name: 'Archive' })).not.toBeInTheDocument();
      // Editing is still allowed for archived records.
      expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    });
  });

  it('shows pagination totals from the API metadata', async () => {
    mockList.mockResolvedValueOnce(
      listResponse([feature()], { page: 1, per_page: 20, total: 57, total_pages: 3 })
    );

    renderPage();
    await screen.findByText('SEC-1');

    // The range reflects the requested page window (1-20), not the number of
    // rows this particular stub returned.
    expect(screen.getByText(/Showing 1-20 of 57 parcels/)).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
  });

  it('disables Previous on the first page and Next on the last page', async () => {
    mockList.mockResolvedValueOnce(
      listResponse([feature()], { page: 1, per_page: 20, total: 57, total_pages: 3 })
    );

    renderPage();
    await screen.findByText('SEC-1');

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
  });
});

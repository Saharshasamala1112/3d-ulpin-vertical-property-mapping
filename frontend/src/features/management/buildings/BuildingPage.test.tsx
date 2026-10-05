import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { BuildingPage } from './BuildingPage';
import { ApiError } from '../../../services/api-error';
import type { Building } from './building-types';

vi.mock('./building-service', () => ({
  listBuildings: vi.fn(),
  deleteBuilding: vi.fn(),
}));

vi.mock('../floors/floor-service', () => ({
  listFloors: vi.fn(),
}));

vi.mock('../../../app/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin' } }),
}));

import { deleteBuilding, listBuildings } from './building-service';
import { listFloors } from '../floors/floor-service';

const mockList = vi.mocked(listBuildings);
const mockDelete = vi.mocked(deleteBuilding);
const mockFloors = vi.mocked(listFloors);

function building(overrides: Partial<Building> = {}): Building {
  return {
    id: 'b-1',
    parcel_id: 'p-1',
    building_identifier: 'BLD-1',
    name: 'Tower A',
    building_type: 'residential',
    construction_status: 'planned',
    footprint_geometry: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderPage(path = '/app/buildings/p-1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/buildings" element={<BuildingPage />} />
        <Route path="/app/buildings/:parcelId" element={<BuildingPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('BuildingPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists buildings for the parcel in the route', async () => {
    mockList.mockResolvedValue([building()]);
    renderPage();

    expect(await screen.findByText('BLD-1')).toBeTruthy();
    expect(mockList).toHaveBeenCalledWith('p-1');
  });

  it('does not call the floor service unless counts are requested', async () => {
    mockList.mockResolvedValue([building()]);
    renderPage();

    await screen.findByText('BLD-1');
    expect(mockFloors).not.toHaveBeenCalled();
  });

  it('derives per-building floor counts when the count column is shown', async () => {
    mockList.mockResolvedValue([building({ id: 'b-1' }), building({ id: 'b-2', building_identifier: 'BLD-2' })]);
    mockFloors.mockImplementation(async (buildingId: string) =>
      buildingId === 'b-1'
        ? ([{ id: 'f-1' }, { id: 'f-2' }] as never)
        : ([{ id: 'f-3' }] as never)
    );
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /show floor counts/i }));

    await waitFor(() => expect(mockFloors).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      const rowA = rows.find((r) => within(r).queryByText('BLD-1'));
      const rowB = rows.find((r) => within(r).queryByText('BLD-2'));
      expect(within(rowA!).getByText('2')).toBeTruthy();
      expect(within(rowB!).getByText('1')).toBeTruthy();
    });
  });

  it('warns about cascading floors and units before a hard delete', async () => {
    mockList.mockResolvedValue([building()]);
    mockDelete.mockResolvedValue(undefined);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /delete/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/also deletes its floors and units/i)).toBeTruthy();
    expect(within(dialog).getByText(/Permanently delete "BLD-1"\?/)).toBeTruthy();
  });

  it('says the delete cannot be undone, unlike the parcel and unit archive flows', async () => {
    mockList.mockResolvedValue([building()]);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /delete/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/cannot be undone/i)).toBeTruthy();
    expect(within(dialog).queryByText(/archive/i)).toBeNull();
  });

  it('surfaces a server error as generic copy instead of leaking the raw detail', async () => {
    mockList.mockRejectedValueOnce(new ApiError({ status: 500, errorCode: 'INTERNAL_ERROR', message: 'server exploded' }));
    renderPage();

    expect(await screen.findByTestId('error-banner-message')).toHaveTextContent(
      /server could not process the request/i
    );
    expect(screen.queryByText(/server exploded/)).toBeNull();
  });

  it('does not claim the list is empty when the load failed', async () => {
    mockList.mockRejectedValueOnce(new ApiError({ status: 500, errorCode: 'INTERNAL_ERROR', message: 'server exploded' }));
    renderPage();

    await screen.findByTestId('error-banner-message');
    expect(screen.queryByText(/no buildings on this parcel/i)).toBeNull();
  });

  it('names the offending fields on a validation error', async () => {
    mockList.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: { building_identifier: 'too long' },
      })
    );
    renderPage();

    expect(await screen.findByTestId('error-banner-message')).toHaveTextContent(/building_identifier/);
  });

  it('reports an unreachable API distinctly', async () => {
    mockList.mockRejectedValueOnce(new ApiError({ status: 0, errorCode: 'NETWORK_ERROR', message: 'Network request failed' }));
    renderPage();

    expect(await screen.findByTestId('error-banner-message')).toHaveTextContent(/could not reach the server/i);
  });

  it('keeps the row and reports the error when a delete fails', async () => {
    mockList.mockResolvedValue([building()]);
    mockDelete.mockRejectedValueOnce(new ApiError({ status: 409, errorCode: 'CONFLICT', message: 'building has floors' }));
    renderPage();
    await screen.findByText('BLD-1');

    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /delete building/i }));

    expect(await within(dialog).findByText(/building has floors/)).toBeTruthy();
    expect(screen.getByText('BLD-1')).toBeTruthy();
  });

  it('prompts the user to pick a parcel when no parcel is in the route', async () => {
    renderPage('/app/buildings');
    expect(await screen.findByText(/parcels/i)).toBeTruthy();
    expect(mockList).not.toHaveBeenCalled();
  });
});

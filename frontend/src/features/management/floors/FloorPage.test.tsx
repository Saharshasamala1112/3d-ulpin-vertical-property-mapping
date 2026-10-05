import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { FloorPage } from './FloorPage';
import type { Floor } from './floor-types';

vi.mock('./floor-service', () => ({
  listFloors: vi.fn(),
  deleteFloor: vi.fn(),
}));

vi.mock('../units/unit-service', () => ({
  listUnits: vi.fn(),
}));

vi.mock('../../../app/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin' } }),
}));

import { deleteFloor, listFloors } from './floor-service';
import { listUnits } from '../units/unit-service';

const mockList = vi.mocked(listFloors);
const mockDelete = vi.mocked(deleteFloor);
const mockUnits = vi.mocked(listUnits);

function floor(overrides: Partial<Floor> = {}): Floor {
  return {
    id: 'f-1',
    building_id: 'b-1',
    floor_number: 1,
    level_name: 'Ground',
    floor_type: 'ground',
    elevation_min: 0,
    elevation_max: 3,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderPage(path = '/app/floors/b-1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/floors" element={<FloorPage />} />
        <Route path="/app/floors/:buildingId" element={<FloorPage />} />
        <Route path="/app/units" element={<div>Units</div>} />
        <Route path="/app/units/:floorId" element={<div>Units</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('FloorPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists floors for the building in the route', async () => {
    mockList.mockResolvedValue([floor()]);
    renderPage();

    expect(await screen.findByRole('link', { name: 'Ground (1)' })).toBeTruthy();
    expect(mockList).toHaveBeenCalledWith('b-1');
  });

  it('does not call the unit service unless counts are requested', async () => {
    mockList.mockResolvedValue([floor()]);
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    expect(mockUnits).not.toHaveBeenCalled();
  });

  it('derives per-floor unit counts when the count column is shown', async () => {
    mockList.mockResolvedValue([floor({ id: 'f-1' }), floor({ id: 'f-2', floor_number: 2, level_name: 'First' })]);
    mockUnits.mockImplementation(async (floorId: string) =>
      floorId === 'f-1'
        ? ([{ id: 'u-1' }, { id: 'u-2' }, { id: 'u-3' }] as never)
        : ([{ id: 'u-4' }] as never)
    );
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    fireEvent.click(screen.getByRole('button', { name: /show unit counts/i }));

    await waitFor(() => expect(mockUnits).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      const rowA = rows.find((r) => within(r).queryByRole('link', { name: 'Ground (1)' }));
      const rowB = rows.find((r) => within(r).queryByRole('link', { name: 'First (2)' }));
      expect(within(rowA!).getByText('3')).toBeTruthy();
      expect(within(rowB!).getByText('1')).toBeTruthy();
    });
  });

  it('marks a count as unavailable instead of reporting zero when the sub-request fails', async () => {
    mockList.mockResolvedValue([floor()]);
    mockUnits.mockRejectedValue(new Error('boom'));
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    fireEvent.click(screen.getByRole('button', { name: /show unit counts/i }));

    const cell = await screen.findByTitle(/could not load units/i);
    expect(cell).toHaveTextContent('n/a');
  });

  it('warns about cascading units before a hard delete', async () => {
    mockList.mockResolvedValue([floor()]);
    mockDelete.mockResolvedValue(undefined);
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    fireEvent.click(screen.getByRole('button', { name: /delete/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/also deletes its units/i)).toBeTruthy();
    expect(within(dialog).getByText(/Permanently delete floor 1\?/)).toBeTruthy();
    expect(within(dialog).queryByText(/archive/i)).toBeNull();
  });

  it('deep-links a floor to its units', async () => {
    mockList.mockResolvedValue([floor()]);
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    const link = screen.getByRole('link', { name: 'Ground (1)' });
    expect(link.getAttribute('href')).toBe('/app/units/f-1');
  });

  it('encodes a floor id that needs escaping', async () => {
    mockList.mockResolvedValue([floor({ id: 'f/1' })]);
    renderPage();
    await screen.findByRole('link', { name: 'Ground (1)' });

    expect(screen.getByRole('link', { name: 'Ground (1)' }).getAttribute('href')).toBe('/app/units/f%2F1');
  });

  it('prompts for a building when no building is in the route', async () => {
    renderPage('/app/floors');
    expect(await screen.findByText(/No building selected/i)).toBeTruthy();
    expect(mockList).not.toHaveBeenCalled();
  });
});

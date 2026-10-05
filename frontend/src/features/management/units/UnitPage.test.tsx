import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { UnitPage } from './UnitPage';
import { ApiError } from '../../../services/api-error';
import type { Unit } from './unit-types';

vi.mock('./unit-service', () => ({
  listUnits: vi.fn(),
  archiveUnit: vi.fn(),
}));

vi.mock('../../../app/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin' } }),
}));

import { archiveUnit, listUnits } from './unit-service';

const mockList = vi.mocked(listUnits);
const mockArchive = vi.mocked(archiveUnit);

function unit(overrides: Partial<Unit> = {}): Unit {
  return {
    id: 'u-1',
    floor_id: 'f-1',
    unit_identifier: 'U-101',
    unit_type: 'residential',
    area_sqm: 85.5,
    x_min: 0,
    x_max: 5,
    y_min: 0,
    y_max: 6,
    z_min: 0,
    z_max: 3,
    status: 'active',
    vdc_code: null,
    vdc_status: 'missing',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderPage(path = '/app/units/f-1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/units" element={<UnitPage />} />
        <Route path="/app/units/:floorId" element={<UnitPage />} />
        <Route path="/app/vdc" element={<div>VDC workspace</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('UnitPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists units for the floor in the route', async () => {
    mockList.mockResolvedValue([unit()]);
    renderPage();

    expect(await screen.findByText('U-101')).toBeTruthy();
    expect(mockList).toHaveBeenCalledWith('f-1');
  });

  it('archives rather than deletes, and says the record is kept', async () => {
    mockList.mockResolvedValue([unit()]);
    mockArchive.mockResolvedValue(undefined);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.click(screen.getByRole('button', { name: /archive/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Set the status of "U-101" to archived\?/)).toBeTruthy();
    expect(within(dialog).queryByText(/cannot be undone/i)).toBeNull();
  });

  it('sends the archive through DELETE', async () => {
    mockList.mockResolvedValue([unit()]);
    mockArchive.mockResolvedValue(undefined);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.click(screen.getByRole('button', { name: /archive/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /archive unit/i }));

    await waitFor(() => expect(mockArchive).toHaveBeenCalledWith('u-1'));
  });

  it('still lists an already-archived unit but offers no archive action for it', async () => {
    mockList.mockResolvedValue([unit({ status: 'archived' })]);
    renderPage();

    expect(await screen.findByText('U-101')).toBeTruthy();
    expect(screen.getByText('archived')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /archive/i })).toBeNull();
  });

  it('shows the stored vdc_code and links to the VDC workspace', async () => {
    mockList.mockResolvedValue([unit({ vdc_code: 'VDC-7' })]);
    renderPage();

    expect(await screen.findByText('VDC-7')).toBeTruthy();
    const link = screen.getByRole('link', { name: 'U-101' });
    expect(link.getAttribute('href')).toBe('/app/vdc');
  });

  it('renders a dash rather than null for a missing vdc_code', async () => {
    mockList.mockResolvedValue([unit({ vdc_code: null })]);
    renderPage();

    await screen.findByText('U-101');
    const row = screen.getByText('U-101').closest('tr')!;
    expect(within(row).getByText('—')).toBeTruthy();
  });

  it('filters the loaded page by search text', async () => {
    mockList.mockResolvedValue([unit({ unit_identifier: 'U-101' }), unit({ id: 'u-2', unit_identifier: 'U-202' })]);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'U-202' } });

    expect(screen.getByText('U-202')).toBeTruthy();
    expect(screen.queryByText('U-101')).toBeNull();
  });

  it('searches the vdc_code too', async () => {
    mockList.mockResolvedValue([
      unit({ id: 'u-1', unit_identifier: 'U-101', vdc_code: null }),
      unit({ id: 'u-2', unit_identifier: 'U-202', vdc_code: 'VDC-9' }),
    ]);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'vdc-9' } });

    expect(screen.getByText('U-202')).toBeTruthy();
    expect(screen.queryByText('U-101')).toBeNull();
  });

  it('filters by status', async () => {
    mockList.mockResolvedValue([
      unit({ id: 'u-1', unit_identifier: 'U-101', status: 'active' }),
      unit({ id: 'u-2', unit_identifier: 'U-202', status: 'sold' }),
    ]);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.change(screen.getByLabelText(/status/i), { target: { value: 'sold' } });

    expect(screen.getByText('U-202')).toBeTruthy();
    expect(screen.queryByText('U-101')).toBeNull();
  });

  it('distinguishes a search miss from an empty floor', async () => {
    mockList.mockResolvedValue([unit()]);
    renderPage();
    await screen.findByText('U-101');

    fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'zzz' } });

    expect(screen.getByText(/no units match your search/i)).toBeTruthy();
    expect(screen.queryByText(/no units in this floor/i)).toBeNull();
  });

  it('keeps the row and reports the error when archiving fails', async () => {
    mockList.mockResolvedValue([unit()]);
    mockArchive.mockRejectedValueOnce(
      new ApiError({ status: 409, errorCode: 'CONFLICT', message: 'unit is referenced' })
    );
    renderPage();
    await screen.findByText('U-101');

    fireEvent.click(screen.getByRole('button', { name: /archive/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /archive unit/i }));

    expect(await within(dialog).findByText(/unit is referenced/)).toBeTruthy();
    expect(screen.getByText('U-101')).toBeTruthy();
  });

  it('prompts for a floor when no floor is in the route', async () => {
    renderPage('/app/units');
    expect(await screen.findByText(/No floor selected/i)).toBeTruthy();
    expect(mockList).not.toHaveBeenCalled();
  });
});

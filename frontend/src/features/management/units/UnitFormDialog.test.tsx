import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UnitFormDialog } from './UnitFormDialog';
import { ApiError } from '../../../services/api-error';
import type { Unit } from './unit-types';

vi.mock('./unit-service', () => ({
  createUnit: vi.fn(),
  updateUnit: vi.fn(),
}));

import { createUnit, updateUnit } from './unit-service';

const mockCreate = vi.mocked(createUnit);
const mockUpdate = vi.mocked(updateUnit);

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

function setValue(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('UnitFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a fully populated create payload, not undefined', async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    mockCreate.mockResolvedValue(unit());

    render(<UnitFormDialog open floorId="f-1" unit={null} onClose={onClose} onSaved={onSaved} />);

    setValue('Unit identifier', 'U-202');
    setValue('Area (sqm)', '42');
    setValue('X min', '0');
    setValue('X max', '5');
    setValue('Y min', '0');
    setValue('Y max', '6');
    setValue('Z min', '0');
    setValue('Z max', '3');
    fireEvent.click(screen.getByRole('button', { name: /^create unit$/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0]).toBe('f-1');
    expect(mockCreate.mock.calls[0][1]).toEqual({
      unit_identifier: 'U-202',
      unit_type: 'residential',
      area_sqm: 42,
      status: 'planned',
      vdc_code: null,
      x_min: 0,
      x_max: 5,
      y_min: 0,
      y_max: 6,
      z_min: 0,
      z_max: 3,
    });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'u-1' }), 'create');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('sends only changed fields on update', async () => {
    const onSaved = vi.fn();
    mockUpdate.mockResolvedValue(unit({ unit_identifier: 'U-999' }));

    render(
      <UnitFormDialog open floorId="f-1" unit={unit()} onClose={vi.fn()} onSaved={onSaved} />
    );

    setValue('Unit identifier', 'U-999');
    fireEvent.click(screen.getByRole('button', { name: /^save changes$/i }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][0]).toBe('u-1');
    expect(mockUpdate.mock.calls[0][1]).toEqual({ unit_identifier: 'U-999' });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ unit_identifier: 'U-999' }), 'update');
  });

  it('does not call the API when client validation fails', async () => {
    render(<UnitFormDialog open floorId="f-1" unit={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    setValue('Unit identifier', 'U-1');
    setValue('Area (sqm)', '10');
    // x_max below x_min is rejected before any request is made.
    setValue('X min', '10');
    setValue('X max', '1');
    setValue('Y min', '0');
    setValue('Y max', '1');
    setValue('Z min', '0');
    setValue('Z max', '1');
    fireEvent.click(screen.getByRole('button', { name: /^create unit$/i }));

    await waitFor(() =>
      expect(screen.getAllByText(/must be strictly less than/i).length).toBeGreaterThan(0)
    );
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it('surfaces a server 422 on the offending field', async () => {
    mockCreate.mockRejectedValue(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: { unit_identifier: 'Unit identifier already exists' },
      })
    );

    render(<UnitFormDialog open floorId="f-1" unit={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    setValue('Unit identifier', 'U-1');
    setValue('Area (sqm)', '10');
    setValue('X min', '0');
    setValue('X max', '1');
    setValue('Y min', '0');
    setValue('Y max', '1');
    setValue('Z min', '0');
    setValue('Z max', '1');
    fireEvent.click(screen.getByRole('button', { name: /^create unit$/i }));

    await waitFor(() =>
      expect(screen.getByText('Unit identifier already exists')).toBeInTheDocument()
    );
  });
});

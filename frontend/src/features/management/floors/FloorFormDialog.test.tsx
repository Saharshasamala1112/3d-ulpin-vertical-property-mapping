import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FloorFormDialog } from './FloorFormDialog';
import { ApiError } from '../../../services/api-error';
import type { Floor } from './floor-types';

vi.mock('./floor-service', () => ({
  createFloor: vi.fn(),
  updateFloor: vi.fn(),
}));

import { createFloor, updateFloor } from './floor-service';

const mockCreate = vi.mocked(createFloor);
const mockUpdate = vi.mocked(updateFloor);

function floor(overrides: Partial<Floor> = {}): Floor {
  return {
    id: 'fl-1',
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

function setValue(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('FloorFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a fully populated create payload', async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    mockCreate.mockResolvedValue(floor());

    render(<FloorFormDialog open buildingId="b-1" floor={null} onClose={onClose} onSaved={onSaved} />);

    setValue('Floor number', '2');
    setValue('Level name', 'First');
    setValue('Minimum elevation (m)', '3');
    setValue('Maximum elevation (m)', '6');
    fireEvent.click(screen.getByRole('button', { name: /^create floor$/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0]).toBe('b-1');
    expect(mockCreate.mock.calls[0][1]).toEqual({
      floor_number: 2,
      level_name: 'First',
      floor_type: 'typical',
      elevation_min: 3,
      elevation_max: 6,
    });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'fl-1' }), 'create');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('sends only changed fields on update', async () => {
    const onSaved = vi.fn();
    mockUpdate.mockResolvedValue(floor({ level_name: 'Mezzanine' }));

    render(<FloorFormDialog open buildingId="b-1" floor={floor()} onClose={vi.fn()} onSaved={onSaved} />);

    setValue('Level name', 'Mezzanine');
    fireEvent.click(screen.getByRole('button', { name: /^save changes$/i }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][0]).toBe('fl-1');
    expect(mockUpdate.mock.calls[0][1]).toEqual({ level_name: 'Mezzanine' });
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ level_name: 'Mezzanine' }),
      'update'
    );
  });

  it('refuses to create without a building', async () => {
    render(<FloorFormDialog open buildingId={null} floor={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    setValue('Floor number', '1');
    setValue('Minimum elevation (m)', '0');
    setValue('Maximum elevation (m)', '3');
    fireEvent.click(screen.getByRole('button', { name: /^create floor$/i }));

    await waitFor(() =>
      expect(screen.getByText(/building must be selected/i)).toBeInTheDocument()
    );
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it('surfaces a server 422 on the offending field', async () => {
    mockCreate.mockRejectedValue(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: { floor_number: 'Floor number must be positive' },
      })
    );

    render(<FloorFormDialog open buildingId="b-1" floor={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    setValue('Floor number', '1');
    setValue('Minimum elevation (m)', '0');
    setValue('Maximum elevation (m)', '3');
    fireEvent.click(screen.getByRole('button', { name: /^create floor$/i }));

    await waitFor(() => expect(screen.getByText('Floor number must be positive')).toBeInTheDocument());
  });
});

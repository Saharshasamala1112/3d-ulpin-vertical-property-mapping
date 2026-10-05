import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BuildingFormDialog } from './BuildingFormDialog';
import { ApiError } from '../../../services/api-error';
import type { Building } from './building-types';

vi.mock('./building-service', () => ({
  createBuilding: vi.fn(),
  updateBuilding: vi.fn(),
}));

import { createBuilding, updateBuilding } from './building-service';

const mockCreate = vi.mocked(createBuilding);
const mockUpdate = vi.mocked(updateBuilding);

const FOOTPRINT = '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}';

function building(overrides: Partial<Building> = {}): Building {
  return {
    id: 'b-1',
    parcel_id: 'p-1',
    building_identifier: 'BLD-1',
    name: 'Main block',
    building_type: 'residential',
    construction_status: 'planned',
    footprint_geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function setValue(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('BuildingFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a fully populated create payload with a parsed footprint', async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    mockCreate.mockResolvedValue(building());

    render(
      <BuildingFormDialog
        open
        parcelId="p-1"
        building={null}
        onClose={onClose}
        onSaved={onSaved}
      />
    );

    setValue('Building identifier', 'BLD-9');
    setValue('Name', 'Annex');
    setValue('Footprint geometry (optional)', FOOTPRINT);
    fireEvent.click(screen.getByRole('button', { name: /^create building$/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0]).toBe('p-1');
    expect(mockCreate.mock.calls[0][1]).toEqual({
      building_identifier: 'BLD-9',
      name: 'Annex',
      building_type: 'residential',
      construction_status: 'planned',
      footprint_geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'b-1' }), 'create');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('sends only changed fields on update and ignores key order in the footprint', async () => {
    const onSaved = vi.fn();
    mockUpdate.mockResolvedValue(building({ name: 'Renamed' }));

    render(
      <BuildingFormDialog
        open
        parcelId="p-1"
        building={building()}
        onClose={vi.fn()}
        onSaved={onSaved}
      />
    );

    setValue('Name', 'Renamed');
    // Same geometry, different key order: must not be sent as a change.
    setValue(
      'Footprint geometry (optional)',
      '{"coordinates":[[[0,0],[1,0],[1,1],[0,0]]],"type":"Polygon"}'
    );
    fireEvent.click(screen.getByRole('button', { name: /^save changes$/i }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][0]).toBe('b-1');
    expect(mockUpdate.mock.calls[0][1]).toEqual({ name: 'Renamed' });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ name: 'Renamed' }), 'update');
  });

  it('refuses to create without a parcel', async () => {
    render(
      <BuildingFormDialog
        open
        parcelId={null}
        building={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />
    );

    setValue('Building identifier', 'BLD-1');
    setValue('Footprint geometry (optional)', FOOTPRINT);
    fireEvent.click(screen.getByRole('button', { name: /^create building$/i }));

    await waitFor(() =>
      expect(screen.getByText(/parcel must be selected/i)).toBeInTheDocument()
    );
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it('rejects malformed footprint GeoJSON before calling the API', async () => {
    render(
      <BuildingFormDialog
        open
        parcelId="p-1"
        building={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />
    );

    setValue('Building identifier', 'BLD-1');
    setValue('Footprint geometry (optional)', '{"type":"Polygon","coordinates":"nope"}');
    fireEvent.click(screen.getByRole('button', { name: /^create building$/i }));

    await waitFor(() => expect(mockCreate).not.toHaveBeenCalled());
    expect(screen.getByText(/polygon/i)).toBeInTheDocument();
  });

  it('accepts any structurally valid geometry, matching the backend contract', async () => {
    // The API types footprint_geometry as `dict[str, Any]` and documents that
    // deep geometry validation is out of scope, so the form only enforces
    // structural GeoJSON validity rather than restricting the geometry type.
    mockCreate.mockResolvedValue(building());
    render(
      <BuildingFormDialog
        open
        parcelId="p-1"
        building={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />
    );

    setValue('Building identifier', 'BLD-1');
    setValue('Footprint geometry (optional)', '{"type":"Point","coordinates":[1,2]}');
    fireEvent.click(screen.getByRole('button', { name: /^create building$/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][1]).toMatchObject({
      footprint_geometry: { type: 'Point', coordinates: [1, 2] },
    });
  });

  it('surfaces a server 422 on the offending field', async () => {
    mockCreate.mockRejectedValue(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: { building_identifier: 'Identifier already exists' },
      })
    );

    render(
      <BuildingFormDialog
        open
        parcelId="p-1"
        building={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />
    );

    setValue('Building identifier', 'BLD-1');
    setValue('Footprint geometry (optional)', FOOTPRINT);
    fireEvent.click(screen.getByRole('button', { name: /^create building$/i }));

    await waitFor(() => expect(screen.getByText('Identifier already exists')).toBeInTheDocument());
  });
});

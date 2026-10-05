import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ParcelFormDialog } from './ParcelFormDialog';
import { ApiError } from '../../../services/api-error';
import type { GeoJSONFeature } from './parcel-types';

vi.mock('./parcel-service', () => ({
  createParcel: vi.fn(),
  updateParcel: vi.fn(),
}));

import { createParcel, updateParcel } from './parcel-service';

const mockCreate = vi.mocked(createParcel);
const mockUpdate = vi.mocked(updateParcel);

const GEOMETRY = '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}';

function parcel(overrides: Partial<GeoJSONFeature> = {}): GeoJSONFeature {
  return {
    type: 'Feature',
    id: 'p-1',
    geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    properties: {
      id: 'p-1',
      parcel_identifier: 'P-1',
      ulpin: 'ABC123',
      area_sqm: 120,
      status: 'active',
      metadata: null,
    },
    ...overrides,
  };
}

function setValue(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function fillRequiredFields() {
  setValue('Parcel identifier', 'P-9');
  setValue('ULPIN', 'XYZ789');
  setValue('Area (sqm)', '250');
  setValue('Geometry', GEOMETRY);
}

describe('ParcelFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a fully populated create payload with a parsed geometry', async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    mockCreate.mockResolvedValue(parcel());

    render(<ParcelFormDialog open parcel={null} onClose={onClose} onSaved={onSaved} />);

    fillRequiredFields();
    setValue('Metadata (optional)', '{"zone":"residential"}');
    fireEvent.click(screen.getByRole('button', { name: /^create parcel$/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0]).toEqual({
      parcel_identifier: 'P-9',
      ulpin: 'XYZ789',
      area_sqm: 250,
      status: 'draft',
      geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
      metadata: { zone: 'residential' },
    });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'p-1' }), 'create');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('sends only changed fields on update and ignores geometry key order', async () => {
    const onSaved = vi.fn();
    mockUpdate.mockResolvedValue(parcel());

    render(<ParcelFormDialog open parcel={parcel()} onClose={vi.fn()} onSaved={onSaved} />);

    setValue('Area (sqm)', '999');
    // Same geometry, reordered keys: must not appear in the update body.
    setValue(
      'Geometry',
      '{"coordinates":[[[0,0],[1,0],[1,1],[0,0]]],"type":"Polygon"}'
    );
    fireEvent.click(screen.getByRole('button', { name: /^save changes$/i }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][0]).toBe('p-1');
    expect(mockUpdate.mock.calls[0][1]).toEqual({ area_sqm: 999 });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'p-1' }), 'update');
  });

  it('rejects a non-object metadata payload before calling the API', async () => {
    render(<ParcelFormDialog open parcel={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    fillRequiredFields();
    setValue('Metadata (optional)', '[1,2,3]');
    fireEvent.click(screen.getByRole('button', { name: /^create parcel$/i }));

    await waitFor(() =>
      expect(screen.getByText('Metadata must be a JSON object.')).toBeInTheDocument()
    );
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it('rejects invalid geometry before calling the API', async () => {
    render(<ParcelFormDialog open parcel={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    setValue('Parcel identifier', 'P-9');
    setValue('ULPIN', 'XYZ789');
    setValue('Area (sqm)', '250');
    setValue('Geometry', '{"type":"Point"}');
    fireEvent.click(screen.getByRole('button', { name: /^create parcel$/i }));

    await waitFor(() => expect(mockCreate).not.toHaveBeenCalled());
  });

  it('translates a server geometry 422 onto the geometry control', async () => {
    // The API reports the payload key `geometry`; the control is `geometryText`.
    mockCreate.mockRejectedValue(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: { geometry: 'Geometry is not a valid Feature' },
      })
    );

    render(<ParcelFormDialog open parcel={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    fillRequiredFields();
    fireEvent.click(screen.getByRole('button', { name: /^create parcel$/i }));

    await waitFor(() =>
      expect(screen.getByText('Geometry is not a valid Feature')).toBeInTheDocument()
    );
  });

  it('requires identifier, ulpin, area and geometry', async () => {
    render(<ParcelFormDialog open parcel={null} onClose={vi.fn()} onSaved={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /^create parcel$/i }));

    await waitFor(() => {
      expect(screen.getByText('Parcel identifier is required.')).toBeInTheDocument();
      expect(screen.getByText('ULPIN is required.')).toBeInTheDocument();
      expect(screen.getByText('Area is required.')).toBeInTheDocument();
    });
    expect(mockCreate).not.toHaveBeenCalled();
  });
});

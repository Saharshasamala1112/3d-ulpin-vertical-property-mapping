import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '../../../services/api-client';
import { archiveUnit, createUnit, getUnit, getUnitVdc, listUnits, updateUnit } from './unit-service';
import type { Unit } from './unit-types';

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);
const mockPut = vi.mocked(apiClient.put);
const mockDelete = vi.mocked(apiClient.delete);

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

const payload = {
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
};

describe('unit-service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('scopes the list to the parent floor', async () => {
    mockGet.mockResolvedValueOnce([]);
    await listUnits('f-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/floors/f-1/units');
  });

  it('uses the item path for a single unit', async () => {
    mockGet.mockResolvedValueOnce(unit());
    await getUnit('u-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/units/u-1');
  });

  it('POSTs to the floor-scoped collection', async () => {
    mockPost.mockResolvedValueOnce(unit());
    await createUnit('f-1', payload);
    expect(mockPost).toHaveBeenCalledWith('/api/v1/floors/f-1/units', payload);
  });

  it('PUTs updates to the item path', async () => {
    mockPut.mockResolvedValueOnce(unit());
    await updateUnit('u-1', { status: 'sold' });
    expect(mockPut).toHaveBeenCalledWith('/api/v1/units/u-1', { status: 'sold' });
  });

  it('archives through DELETE rather than removing the record', async () => {
    mockDelete.mockResolvedValueOnce(undefined);
    await expect(archiveUnit('u-1')).resolves.toBeUndefined();
    expect(mockDelete).toHaveBeenCalledWith('/api/v1/units/u-1');
  });

  it('reads the VDC sub-resource', async () => {
    mockGet.mockResolvedValueOnce({ unit_id: 'u-1', vdc_code: 'VDC-1' });
    await expect(getUnitVdc('u-1')).resolves.toEqual({ unit_id: 'u-1', vdc_code: 'VDC-1' });
    expect(mockGet).toHaveBeenCalledWith('/api/v1/units/u-1/vdc');
  });

  it('propagates API errors', async () => {
    mockDelete.mockRejectedValueOnce(new Error('nope'));
    await expect(archiveUnit('u-1')).rejects.toThrow('nope');
  });
});

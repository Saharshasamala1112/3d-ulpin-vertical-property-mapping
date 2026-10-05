import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '../../../services/api-client';
import { createFloor, deleteFloor, getFloor, listFloors, updateFloor } from './floor-service';
import type { Floor } from './floor-types';

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);
const mockPut = vi.mocked(apiClient.put);
const mockDelete = vi.mocked(apiClient.delete);

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

const payload = {
  floor_number: 1,
  level_name: 'Ground' as string,
  floor_type: 'ground',
  elevation_min: 0,
  elevation_max: 3,
};

describe('floor-service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('scopes the list to the parent building', async () => {
    mockGet.mockResolvedValueOnce([]);
    await listFloors('b-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/buildings/b-1/floors');
  });

  it('uses the item path for a single floor', async () => {
    mockGet.mockResolvedValueOnce(floor());
    await getFloor('f-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/floors/f-1');
  });

  it('POSTs to the building-scoped collection', async () => {
    mockPost.mockResolvedValueOnce(floor());
    await createFloor('b-1', payload);
    expect(mockPost).toHaveBeenCalledWith('/api/v1/buildings/b-1/floors', payload);
  });

  it('PUTs updates to the item path', async () => {
    mockPut.mockResolvedValueOnce(floor());
    await updateFloor('f-1', { level_name: 'Mezzanine' });
    expect(mockPut).toHaveBeenCalledWith('/api/v1/floors/f-1', { level_name: 'Mezzanine' });
  });

  it('hard-deletes via DELETE and tolerates a 204 with no body', async () => {
    mockDelete.mockResolvedValueOnce(undefined);
    await expect(deleteFloor('f-1')).resolves.toBeUndefined();
    expect(mockDelete).toHaveBeenCalledWith('/api/v1/floors/f-1');
  });

  it('propagates API errors', async () => {
    mockDelete.mockRejectedValueOnce(new Error('nope'));
    await expect(deleteFloor('f-1')).rejects.toThrow('nope');
  });
});

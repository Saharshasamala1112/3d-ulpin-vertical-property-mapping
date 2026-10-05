import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '../../../services/api-client';
import { createBuilding, deleteBuilding, getBuilding, listBuildings, updateBuilding } from './building-service';
import type { Building } from './building-types';

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);
const mockPut = vi.mocked(apiClient.put);
const mockDelete = vi.mocked(apiClient.delete);

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

const payload = {
  building_identifier: 'BLD-1',
  name: null,
  building_type: 'residential' as const,
  construction_status: 'planned' as const,
  footprint_geometry: null,
};

describe('building-service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('scopes the list to the parent parcel', async () => {
    mockGet.mockResolvedValueOnce([]);
    await listBuildings('p-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels/p-1/buildings');
  });

  it('uses the item path for a single building', async () => {
    mockGet.mockResolvedValueOnce(building());
    await getBuilding('b-1');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/buildings/b-1');
  });

  it('POSTs to the parcel-scoped collection', async () => {
    mockPost.mockResolvedValueOnce(building());
    await createBuilding('p-1', payload);
    expect(mockPost).toHaveBeenCalledWith('/api/v1/parcels/p-1/buildings', payload);
  });

  it('PUTs updates to the item path', async () => {
    mockPut.mockResolvedValueOnce(building());
    await updateBuilding('b-1', { name: 'Tower B' });
    expect(mockPut).toHaveBeenCalledWith('/api/v1/buildings/b-1', { name: 'Tower B' });
  });

  it('hard-deletes via DELETE and tolerates a 204 with no body', async () => {
    mockDelete.mockResolvedValueOnce(undefined);
    await expect(deleteBuilding('b-1')).resolves.toBeUndefined();
    expect(mockDelete).toHaveBeenCalledWith('/api/v1/buildings/b-1');
  });

  it('propagates the API error rather than swallowing it', async () => {
    mockDelete.mockRejectedValueOnce(new Error('boom'));
    await expect(deleteBuilding('b-1')).rejects.toThrow('boom');
  });

  it('encodes ids that need escaping', async () => {
    mockGet.mockResolvedValueOnce([]);
    await listBuildings('parcel/../secret');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels/parcel%2F..%2Fsecret/buildings');
  });
});

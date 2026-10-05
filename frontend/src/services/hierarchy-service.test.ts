import { describe, it, expect, beforeEach, vi } from 'vitest';
import { hierarchyService } from './hierarchy-service';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from './api-client';

const mockGet = vi.mocked(apiClient.get);

describe('hierarchyService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists parcels from the paginated response', async () => {
    mockGet.mockResolvedValueOnce({
      data: [
        {
          id: 'parcel-1',
          properties: {
            id: 'parcel-1',
            parcel_identifier: 'P-1',
            ulpin: 'ULPIN-1',
          },
        },
      ],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });

    const parcels = await hierarchyService.listParcels();

    expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels?page=1&per_page=100');
    expect(parcels).toEqual([{ id: 'parcel-1', label: 'ULPIN-1' }]);
  });

  it('labels buildings by name with identifier fallback', async () => {
    mockGet.mockResolvedValueOnce([
      { id: 'b1', building_identifier: 'B-1', name: 'Tower A' },
      { id: 'b2', building_identifier: 'B-2', name: null },
    ]);

    const buildings = await hierarchyService.listBuildings('parcel-1');

    expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels/parcel-1/buildings');
    expect(buildings).toEqual([
      { id: 'b1', label: 'Tower A' },
      { id: 'b2', label: 'B-2' },
    ]);
  });

  it('labels floors by level name with floor number fallback', async () => {
    mockGet.mockResolvedValueOnce([
      { id: 'f1', floor_number: 3, level_name: 'Third floor' },
      { id: 'f2', floor_number: 4, level_name: null },
    ]);

    const floors = await hierarchyService.listFloors('building-1');

    expect(mockGet).toHaveBeenCalledWith('/api/v1/buildings/building-1/floors');
    expect(floors).toEqual([
      { id: 'f1', label: 'Third floor' },
      { id: 'f2', label: 'Floor 4' },
    ]);
  });

  it('lists units of a floor', async () => {
    mockGet.mockResolvedValueOnce([{ id: 'u1', unit_identifier: 'A-101' }]);

    const units = await hierarchyService.listUnits('floor-1');

    expect(mockGet).toHaveBeenCalledWith('/api/v1/floors/floor-1/units');
    expect(units).toEqual([{ id: 'u1', label: 'A-101' }]);
  });

  it('collects every unit id of a building for the status handoff', async () => {
    mockGet
      .mockResolvedValueOnce([
        { id: 'f1', floor_number: 1, level_name: null },
        { id: 'f2', floor_number: 2, level_name: null },
      ])
      .mockResolvedValueOnce([{ id: 'u1', unit_identifier: 'A-101' }])
      .mockResolvedValueOnce([
        { id: 'u2', unit_identifier: 'B-201' },
        { id: 'u3', unit_identifier: 'B-202' },
      ]);

    const ids = await hierarchyService.listBuildingUnitIds('building-1');

    expect(ids).toEqual(['u1', 'u2', 'u3']);
  });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getUnitGeometry,
  isNotFoundError,
  listBuildings,
  listFloors,
  listParcels,
  listUnits,
  loadBuildingScene,
  toErrorMessage,
} from './geometry-service';
import { toUnitGeometry, type GeometryWire } from '../types/geometry';

vi.mock('./api-client', () => ({
  apiClient: { get: vi.fn() },
}));

import { apiClient } from './api-client';

const mockGet = vi.mocked(apiClient.get);

const GEOMETRY_WIRE: GeometryWire = {
  id: 'geo-1',
  unit_id: 'unit-1',
  x_min: '1.123456',
  x_max: '5.654321',
  y_min: '2.500000',
  y_max: '7.250000',
  z_min: '0.100000',
  z_max: '3.141593',
  geometry_type: 'aabb',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  volume: '65.459974522738750000',
  centroid: ['3.3888885', '4.875000', '1.6207965'],
  dimensions: ['4.530865', '4.750000', '3.041593'],
};

function apiError(status: number, data: unknown) {
  return { status, data };
}

describe('geometry-service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('listParcels', () => {
    it('unwraps the GeoJSON feature envelope', async () => {
      mockGet.mockResolvedValueOnce({
        data: [
          {
            type: 'Feature',
            id: 'p-1',
            geometry: { type: 'MultiPolygon', coordinates: [] },
            properties: { id: 'p-1', parcel_identifier: 'PARCEL-1', ulpin: 'ULPIN-1' },
          },
        ],
        meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
      });

      await expect(listParcels()).resolves.toEqual([
        { id: 'p-1', identifier: 'PARCEL-1', ulpin: 'ULPIN-1' },
      ]);
      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels?page=1&per_page=100');
    });
  });

  describe('listBuildings', () => {
    it('requests the parcel hierarchy and maps fields', async () => {
      mockGet.mockResolvedValueOnce([
        {
          id: 'b-1',
          building_identifier: 'BLDG-1',
          name: 'Tower',
          building_type: 'residential',
          construction_status: 'completed',
        },
      ]);

      await expect(listBuildings('p-1')).resolves.toEqual([
        {
          id: 'b-1',
          identifier: 'BLDG-1',
          name: 'Tower',
          buildingType: 'residential',
          constructionStatus: 'completed',
        },
      ]);
      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels/p-1/buildings');
    });
  });

  describe('listFloors and listUnits', () => {
    it('maps floors', async () => {
      mockGet.mockResolvedValueOnce([
        { id: 'f-1', floor_number: 2, level_name: 'Typical', floor_type: 'typical' },
      ]);

      await expect(listFloors('b-1')).resolves.toEqual([
        { id: 'f-1', floorNumber: 2, levelName: 'Typical', floorType: 'typical' },
      ]);
      expect(mockGet).toHaveBeenCalledWith('/api/v1/buildings/b-1/floors');
    });

    it('maps units', async () => {
      mockGet.mockResolvedValueOnce([
        { id: 'u-1', unit_identifier: 'A-101', unit_type: 'residential', status: 'active' },
      ]);

      await expect(listUnits('f-1')).resolves.toEqual([
        { id: 'u-1', unitIdentifier: 'A-101', unitType: 'residential', status: 'active' },
      ]);
      expect(mockGet).toHaveBeenCalledWith('/api/v1/floors/f-1/units');
    });
  });

  describe('getUnitGeometry', () => {
    it('converts the string decimals to numbers at the API boundary', async () => {
      mockGet.mockResolvedValueOnce(GEOMETRY_WIRE);

      const geometry = await getUnitGeometry('unit-1');

      expect(mockGet).toHaveBeenCalledWith('/api/v1/units/unit-1/geometry');
      expect(geometry).toEqual({
        id: 'geo-1',
        unitId: 'unit-1',
        geometryType: 'aabb',
        bounds: {
          min: { x: 1.123456, y: 2.5, z: 0.1 },
          max: { x: 5.654321, y: 7.25, z: 3.141593 },
        },
        centroid: { x: 3.3888885, y: 4.875, z: 1.6207965 },
        dimensions: { x: 4.530865, y: 4.75, z: 3.041593 },
        volume: 65.45997452273875,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-02T00:00:00Z',
      });
    });

    it('returns null when the unit has no geometry', async () => {
      mockGet.mockRejectedValueOnce(
        apiError(404, { error_code: 'NOT_FOUND', message: 'Geometry not found', details: {} }),
      );

      await expect(getUnitGeometry('unit-1')).resolves.toBeNull();
    });

    it('propagates real failures', async () => {
      mockGet.mockRejectedValueOnce(apiError(500, { error_code: 'INTERNAL', message: 'boom' }));

      await expect(getUnitGeometry('unit-1')).rejects.toMatchObject({ status: 500 });
    });
  });

  describe('loadBuildingScene', () => {
    const building = {
      id: 'b-1',
      identifier: 'BLDG-1',
      name: 'Tower',
      buildingType: 'residential',
      constructionStatus: 'completed',
    };

    it('walks floors and units and splits units with and without geometry', async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === '/api/v1/buildings/b-1/floors') {
          return Promise.resolve([
            { id: 'f-1', floor_number: 1, level_name: 'Ground', floor_type: 'ground' },
            { id: 'f-2', floor_number: 2, level_name: 'Typical', floor_type: 'typical' },
          ]);
        }
        if (url === '/api/v1/floors/f-1/units') {
          return Promise.resolve([
            { id: 'u-1', unit_identifier: 'A-101', unit_type: 'residential', status: 'active' },
          ]);
        }
        if (url === '/api/v1/floors/f-2/units') {
          return Promise.resolve([
            { id: 'u-2', unit_identifier: 'B-201', unit_type: 'commercial', status: 'active' },
          ]);
        }
        if (url === '/api/v1/units/u-1/geometry') {
          return Promise.resolve({ ...GEOMETRY_WIRE, id: 'geo-1', unit_id: 'u-1' });
        }
        return Promise.reject(apiError(404, { error_code: 'NOT_FOUND', message: 'Geometry not found' }));
      });

      const scene = await loadBuildingScene(building);

      expect(scene.building).toEqual(building);
      expect(scene.floors).toHaveLength(2);
      expect(scene.units).toHaveLength(1);
      expect(scene.units[0]).toMatchObject({
        id: 'u-1',
        unitIdentifier: 'A-101',
        unitType: 'residential',
        status: 'active',
        floor: { id: 'f-1', levelName: 'Ground' },
      });
      expect(scene.units[0].geometry.dimensions.x).toBe(4.530865);
      expect(scene.unitsWithoutGeometry).toEqual([
        { id: 'u-2', unitIdentifier: 'B-201', floor: { id: 'f-2', floorNumber: 2, levelName: 'Typical', floorType: 'typical' } },
      ]);
    });

    it('returns an empty scene for a building with no units', async () => {
      mockGet.mockImplementation((url: string) =>
        url === '/api/v1/buildings/b-1/floors' ? Promise.resolve([]) : Promise.reject(new Error('unexpected')),
      );

      const scene = await loadBuildingScene(building);

      expect(scene.units).toEqual([]);
      expect(scene.unitsWithoutGeometry).toEqual([]);
    });
  });

  describe('error helpers', () => {
    it('detects 404 rejections', () => {
      expect(isNotFoundError(apiError(404, {}))).toBe(true);
      expect(isNotFoundError(apiError(500, {}))).toBe(false);
      expect(isNotFoundError(new Error('boom'))).toBe(false);
      expect(isNotFoundError(null)).toBe(false);
    });

    it('reads the geometry error envelope message', () => {
      expect(toErrorMessage(apiError(404, { error_code: 'NOT_FOUND', message: 'Geometry not found' }), 'fallback')).toBe(
        'Geometry not found',
      );
    });

    it('reads the nested error envelope used by other endpoints', () => {
      expect(
        toErrorMessage(apiError(409, { error: { code: 'DUPLICATE', message: 'Duplicate parcel' } }), 'fallback'),
      ).toBe('Duplicate parcel');
    });

    it('falls back when the payload has no usable message', () => {
      expect(toErrorMessage(apiError(500, { error_code: 'INTERNAL' }), 'fallback')).toBe('fallback');
      expect(toErrorMessage('nope', 'fallback')).toBe('fallback');
      expect(toErrorMessage(undefined, 'fallback')).toBe('fallback');
    });
  });
});

describe('toUnitGeometry', () => {
  it('rejects non-numeric coordinates rather than rendering NaN geometry', () => {
    expect(() => toUnitGeometry({ ...GEOMETRY_WIRE, x_min: 'not-a-number' })).toThrow(/x_min/);
    expect(() => toUnitGeometry({ ...GEOMETRY_WIRE, centroid: ['1.0', 'oops', '1.0'] })).toThrow(/centroid\.y/);
    expect(() => toUnitGeometry({ ...GEOMETRY_WIRE, volume: '' })).toThrow(/volume/);
  });
});

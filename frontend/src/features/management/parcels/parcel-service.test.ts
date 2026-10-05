import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../services/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from '../../../services/api-client';
import {
  archiveParcel,
  createParcel,
  importBuildingsGeoJSON,
  importParcelsGeoJSON,
  listParcels,
  updateParcel,
} from './parcel-service';
import type { GeoJSONFeature, ParcelListResponse } from './parcel-types';

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);
const mockPut = vi.mocked(apiClient.put);
const mockDelete = vi.mocked(apiClient.delete);

function feature(overrides: Partial<GeoJSONFeature['properties']> = {}): GeoJSONFeature {
  return {
    type: 'Feature',
    id: 'parcel-1',
    geometry: { type: 'MultiPolygon', coordinates: [] },
    properties: {
      id: 'parcel-1',
      parcel_identifier: 'SEC-1',
      ulpin: 'ULPIN-1',
      area_sqm: 100,
      status: 'draft',
      metadata: null,
      ...overrides,
    },
  };
}

describe('parcel-service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('listParcels', () => {
    it('omits all query parameters when called with no arguments', async () => {
      const payload: ParcelListResponse = { data: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } };
      mockGet.mockResolvedValueOnce(payload);

      await listParcels();

      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels');
    });

    it('sends page, per_page and the aliased `status` filter', async () => {
      mockGet.mockResolvedValueOnce({ data: [], meta: {} });

      await listParcels({ page: 3, perPage: 50, status: 'active' });

      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels?page=3&per_page=50&status=active');
    });

    it('omits `status` when the filter is null or empty', async () => {
      mockGet.mockResolvedValue({ data: [], meta: {} });

      await listParcels({ page: 1, status: null });
      expect(mockGet).toHaveBeenLastCalledWith('/api/v1/parcels?page=1');

      await listParcels({ page: 1, status: '' });
      expect(mockGet).toHaveBeenLastCalledWith('/api/v1/parcels?page=1');
    });

    it('clamps per_page to the API maximum of 100 instead of sending an invalid value', async () => {
      mockGet.mockResolvedValue({ data: [], meta: {} });

      await listParcels({ perPage: 500 });

      // The API declares `per_page: Query(ge=1, le=100)` and would 422 on 500.
      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels?per_page=100');
    });

    it('raises per_page to the API minimum of 1 instead of sending 0', async () => {
      mockGet.mockResolvedValue({ data: [], meta: {} });

      await listParcels({ perPage: 0 });

      expect(mockGet).toHaveBeenCalledWith('/api/v1/parcels?per_page=1');
    });
  });

  describe('createParcel', () => {
    it('POSTs the payload and returns the saved feature', async () => {
      mockPost.mockResolvedValueOnce(feature());

      const payload = {
        parcel_identifier: 'SEC-1',
        ulpin: 'ULPIN-1',
        geometry: { type: 'MultiPolygon', coordinates: [] },
        area_sqm: 100,
        status: 'draft',
        metadata: null,
      };

      const result = await createParcel(payload);

      expect(mockPost).toHaveBeenCalledWith('/api/v1/parcels', payload);
      expect(result.properties.parcel_identifier).toBe('SEC-1');
    });
  });

  describe('updateParcel', () => {
    it('PUTs to the id-scoped endpoint and URL-encodes the id', async () => {
      mockPut.mockResolvedValueOnce(feature({ parcel_identifier: 'SEC-2' }));

      await updateParcel('a b/c', { status: 'active' });

      expect(mockPut).toHaveBeenCalledWith('/api/v1/parcels/a%20b%2Fc', { status: 'active' });
    });
  });

  describe('archiveParcel', () => {
    it('issues a DELETE to the id-scoped endpoint', async () => {
      mockDelete.mockResolvedValueOnce(undefined);

      await archiveParcel('parcel-1');

      expect(mockDelete).toHaveBeenCalledWith('/api/v1/parcels/parcel-1');
    });
  });

  describe('GeoJSON import', () => {
    const collection = {
      type: 'FeatureCollection' as const,
      features: [{ type: 'Feature', properties: {}, geometry: null }],
    };

    it('sends parcel preview options and configured ULPIN property', async () => {
      mockPost.mockResolvedValueOnce({ dry_run: true });

      await importParcelsGeoJSON(collection, { dryRun: true, ulpinProperty: 'cadastre_id' });

      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/parcels/import?dry_run=true&ulpin_property=cadastre_id',
        collection
      );
    });

    it('sends the default parcel target for a building import when supplied', async () => {
      mockPost.mockResolvedValueOnce({ dry_run: false });

      await importBuildingsGeoJSON(collection, {
        dryRun: false,
        parcelId: 'parcel-1',
      });

      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/buildings/import?dry_run=false&parcel_id=parcel-1',
        collection
      );
    });
  });
});

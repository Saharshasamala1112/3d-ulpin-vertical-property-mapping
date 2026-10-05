import { describe, it, expect, beforeEach, vi } from 'vitest';
import { topologyService } from './topology-service';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from './api-client';

const mockPost = vi.mocked(apiClient.post);

const report = {
  summary: {
    status: 'passed' as const,
    valid: true,
    geometry_error_count: 0,
    overlap_count: 0,
    gap_count: 0,
    elevation_error_count: 0,
  },
  geometry_errors: [],
  overlap_results: [],
  gap_results: [],
  elevation_errors: [],
};

describe('topologyService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts to the building validate endpoint', async () => {
    mockPost.mockResolvedValueOnce(report);

    const result = await topologyService.validateBuilding('building-1');

    expect(mockPost).toHaveBeenCalledWith(
      '/api/v1/topology/validate/building/building-1'
    );
    expect(result.summary.status).toBe('passed');
  });

  it('posts to the unit validate endpoint', async () => {
    mockPost.mockResolvedValueOnce(report);

    await topologyService.validateUnit('unit-1');

    expect(mockPost).toHaveBeenCalledWith('/api/v1/topology/validate/unit/unit-1');
    expect(mockPost).toHaveBeenCalledTimes(1);
  });

  it('propagates API errors unchanged so callers can classify them', async () => {
    const apiError = {
      status: 404,
      data: { error: { code: 'NOT_FOUND', message: 'Building not found' } },
    };
    mockPost.mockRejectedValueOnce(apiError);

    await expect(topologyService.validateBuilding('missing')).rejects.toEqual(apiError);
  });
});

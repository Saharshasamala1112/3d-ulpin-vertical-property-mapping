import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ownershipService } from './ownership-service';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    request: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from './api-client';

describe('ownershipService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('uses the shared API client for owner search', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [], meta: {} });
    await ownershipService.listOwners('North & East');
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/ownership/owners?search=North%20%26%20East',
    );
  });

  it('sends complete transfer allocations to the ownership API', async () => {
    const body = {
      subject_type: 'unit' as const,
      subject_id: 'unit-id',
      effective_at: '2026-09-30T12:00:00Z',
      allocations: [{ owner_id: 'owner-id', share_basis_points: 10000 }],
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ closed: [], created: [] });
    await ownershipService.transfer(body);
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/ownership/transfers', body);
  });
});

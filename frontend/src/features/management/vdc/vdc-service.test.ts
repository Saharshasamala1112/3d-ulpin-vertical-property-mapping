import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '../../../services/api-client';
import {
  generateUnitVdc,
  generateVdc,
  getUnitVdc,
  parseVdc,
  validateVdc,
} from './vdc-service';
import { canonicalVdc } from './vdc-types';

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);

function unitVdc(overrides: Record<string, unknown> = {}) {
  return {
    unit_id: 'u-1',
    vdc_code: 'GEOSX00001-A-G-1-ZY',
    status: 'present',
    ulpin: 'GEOSX00001',
    domain: 'A',
    level: 'G',
    unit: '1',
    checksum: 'ZY',
    ...overrides,
  };
}

describe('vdc-service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('reads the unit VDC sub-resource', async () => {
    mockGet.mockResolvedValueOnce(unitVdc());
    await expect(getUnitVdc('u-1')).resolves.toEqual(unitVdc());
    expect(mockGet).toHaveBeenCalledWith('/api/v1/units/u-1/vdc');
  });

  it('generates a unit VDC without a request body', async () => {
    mockPost.mockResolvedValueOnce(unitVdc());
    await expect(generateUnitVdc('u-1')).resolves.toEqual(unitVdc());
    expect(mockPost).toHaveBeenCalledWith('/api/v1/units/u-1/vdc');
  });

  it('encodes path segments so an id cannot break out of the path', async () => {
    mockGet.mockResolvedValueOnce(unitVdc());
    await getUnitVdc('a/../b');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/units/a%2F..%2Fb/vdc');
  });

  it('validates with the code as the request body', async () => {
    mockPost.mockResolvedValueOnce({ valid: true, errors: [] });
    await expect(validateVdc('GEOSX00001-A-G-1-ZY')).resolves.toEqual({ valid: true, errors: [] });
    expect(mockPost).toHaveBeenCalledWith('/api/v1/vdc/validate', {
      vdc: 'GEOSX00001-A-G-1-ZY',
    });
  });

  it('resolves for an invalid VDC instead of throwing', async () => {
    // The backend answers 200 with valid: false; that must not become an error.
    mockPost.mockResolvedValueOnce({
      valid: false,
      errors: [{ segment: 'checksum', code: 'checksum_mismatch', message: 'Checksum mismatch' }],
    });

    await expect(validateVdc('GEOSX00001-A-G-1-QQ')).resolves.toMatchObject({ valid: false });
  });

  it('parses a VDC into its five segments', async () => {
    const parsed = { ulpin: 'GEOSX00001', domain: 'A', level: 'G', unit: '1', checksum: 'ZY' };
    mockPost.mockResolvedValueOnce(parsed);

    await expect(parseVdc('GEOSX00001-A-G-1-ZY')).resolves.toEqual(parsed);
    expect(mockPost).toHaveBeenCalledWith('/api/v1/vdc/parse', { vdc: 'GEOSX00001-A-G-1-ZY' });
  });

  it('generates from the four hierarchy components', async () => {
    mockPost.mockResolvedValueOnce({ vdc: 'GEOSX00001-A-G-1-ZY' });

    await expect(
      generateVdc({ ulpin: 'GEOSX00001', domain: 'A', level: 'G', unit: '1' }),
    ).resolves.toEqual({ vdc: 'GEOSX00001-A-G-1-ZY' });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/vdc/generate', {
      ulpin: 'GEOSX00001',
      domain: 'A',
      level: 'G',
      unit: '1',
    });
  });

  it('rebuilds the canonical form by joining the segments in order', () => {
    expect(
      canonicalVdc({ ulpin: 'GEOSX00001', domain: 'A', level: 'G', unit: '1', checksum: 'ZY' }),
    ).toBe('GEOSX00001-A-G-1-ZY');
  });

  it('propagates API errors untouched', async () => {
    mockPost.mockRejectedValueOnce(new Error('nope'));
    await expect(parseVdc('bad')).rejects.toThrow('nope');
  });
});

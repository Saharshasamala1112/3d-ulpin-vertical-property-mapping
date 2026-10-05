import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ApiClient } from './api-client';
import { ApiError } from './api-error';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function textResponse(body: string, init: ResponseInit = {}): Response {
  return new Response(body, { status: 200, ...init });
}

describe('ApiClient', () => {
  const fetchMock = vi.fn();
  let client: ApiClient;

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    localStorage.clear();
    client = new ApiClient('/api-root');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prefixes the endpoint with the base URL and serializes the body', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'p-1' }));

    const result = await client.post<{ id: string }>('/api/v1/parcels', { ulpin: 'ABC' });

    expect(result).toEqual({ id: 'p-1' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api-root/api/v1/parcels');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"ulpin":"ABC"}');
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('omits the body entirely when none is supplied', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    await client.get('/api/v1/parcels');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBeUndefined();
    expect(init.method).toBe('GET');
  });

  it.each([204, 205])('returns undefined for a %i response with no body', async (status) => {
    fetchMock.mockResolvedValue(new Response(null, { status }));

    await expect(client.delete('/api/v1/parcels/p-1')).resolves.toBeUndefined();
  });

  it('returns undefined for an empty 200 body instead of throwing', async () => {
    fetchMock.mockResolvedValue(textResponse(''));

    await expect(client.delete('/api/v1/parcels/p-1')).resolves.toBeUndefined();
  });

  it('returns raw text when the body is not JSON', async () => {
    fetchMock.mockResolvedValue(textResponse('plain text body'));

    await expect(client.get('/api/v1/thing')).resolves.toBe('plain text body');
  });

  it('attaches the bearer token when one is stored', async () => {
    localStorage.setItem('geosix-access-token', 'access-1');
    fetchMock.mockResolvedValue(jsonResponse({}));

    await client.get('/api/v1/parcels');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe('Bearer access-1');
  });

  it('omits the Authorization header when no token is stored', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));

    await client.get('/api/v1/parcels');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it('normalizes a Feature 12 error payload', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error_code: 'VALIDATION_ERROR',
          message: 'Validation failed',
          details: { ulpin: 'ULPIN is required' },
        },
        { status: 422 }
      )
    );

    const error = await client.post('/api/v1/parcels', {}).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.errorCode).toBe('VALIDATION_ERROR');
    expect(apiError.isValidationError).toBe(true);
    expect(apiError.fieldErrors.ulpin).toBe('ULPIN is required');
  });

  it('normalizes a legacy detail payload', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Not found' }, { status: 404 }));

    const error = (await client.get('/api/v1/parcels/x').catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
    expect(error.displayMessage).toBe('Not found');
  });

  it('normalizes a non-JSON error body', async () => {
    fetchMock.mockResolvedValue(textResponse('Internal Server Error', { status: 500 }));

    const error = (await client.get('/api/v1/parcels').catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(500);
  });

  it('normalizes a transport failure into ApiError', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = (await client.get('/api/v1/parcels').catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.errorCode).toBe('NETWORK_ERROR');
  });

  it('refreshes and retries once after a 401 when a refresh token exists', async () => {
    localStorage.setItem('geosix-access-token', 'stale');
    localStorage.setItem('geosix-refresh-token', 'refresh-1');

    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh', refresh_token: 'refresh-2' })
      )
      .mockResolvedValueOnce(jsonResponse({ id: 'p-1' }));

    const result = await client.get<{ id: string }>('/api/v1/parcels/p-1');

    expect(result).toEqual({ id: 'p-1' });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(localStorage.getItem('geosix-access-token')).toBe('fresh');
    expect(localStorage.getItem('geosix-refresh-token')).toBe('refresh-2');
    const retryInit = fetchMock.mock.calls[2][1];
    expect(retryInit.headers.Authorization).toBe('Bearer fresh');
  });

  it('does not attempt a refresh without a refresh token', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'expired' }, { status: 401 }));

    const error = (await client.get('/api/v1/parcels').catch((e: unknown) => e)) as ApiError;

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(error.status).toBe(401);
  });

  it('does not retry when the refresh call itself fails', async () => {
    localStorage.setItem('geosix-refresh-token', 'refresh-1');
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ detail: 'bad refresh' }, { status: 401 }));

    const error = (await client.get('/api/v1/parcels').catch((e: unknown) => e)) as ApiError;

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(error.status).toBe(401);
  });

  it('throws the retried error when the retry is still not ok', async () => {
    localStorage.setItem('geosix-refresh-token', 'refresh-1');
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh', refresh_token: 'refresh-2' })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'forbidden' }, { status: 403 }));

    const error = (await client.get('/api/v1/parcels').catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(403);
  });
});

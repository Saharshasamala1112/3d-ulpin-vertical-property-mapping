import { describe, it, expect } from 'vitest';
import { toApiError } from './api-error';

describe('toApiError', () => {
  it('maps a NOT_FOUND envelope to not_found', () => {
    const view = toApiError({
      status: 404,
      data: { error: { code: 'NOT_FOUND', message: 'Building not found' } },
    });
    expect(view.kind).toBe('not_found');
    expect(view.code).toBe('NOT_FOUND');
    expect(view.message).toBe('Building not found');
    expect(view.status).toBe(404);
  });

  it('maps a 404 without the error envelope to unavailable', () => {
    const view = toApiError({ status: 404, data: { detail: 'Not Found' } });
    expect(view.kind).toBe('unavailable');
    expect(view.code).toBe('ENDPOINT_UNAVAILABLE');
  });

  it('maps a 404 with a null body to unavailable', () => {
    const view = toApiError({ status: 404, data: null });
    expect(view.kind).toBe('unavailable');
  });

  it('maps 401 to auth', () => {
    const view = toApiError({ status: 401, data: null });
    expect(view.kind).toBe('auth');
    expect(view.message).toMatch(/session has expired/i);
  });

  it('maps 403 to a permission error instead of an expired session', () => {
    const view = toApiError({ status: 403, data: null });
    expect(view.kind).toBe('auth');
    expect(view.code).toBe('FORBIDDEN');
    expect(view.message).toMatch(/does not have permission/i);
  });

  it('maps 500 with an envelope message to server', () => {
    const view = toApiError({
      status: 500,
      data: { error: { code: 'INTERNAL', message: 'Boom' } },
    });
    expect(view.kind).toBe('server');
    expect(view.message).toBe('Boom');
  });

  it('maps a fetch TypeError to network', () => {
    const view = toApiError(new TypeError('Failed to fetch'));
    expect(view.kind).toBe('network');
    expect(view.code).toBe('NETWORK_ERROR');
  });

  it('falls back to unknown for unrecognized input', () => {
    const view = toApiError(undefined);
    expect(view.kind).toBe('unknown');
    expect(view.message).toMatch(/unknown reason/i);
  });

  it('uses a FastAPI detail string as the message', () => {
    const view = toApiError({ status: 400, data: { detail: 'Bad params' } });
    expect(view.kind).toBe('unknown');
    expect(view.message).toBe('Bad params');
  });
});

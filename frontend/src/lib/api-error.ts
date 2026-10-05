export type ApiErrorKind =
  | 'not_found'
  | 'unavailable'
  | 'auth'
  | 'server'
  | 'network'
  | 'unknown';

export interface ApiErrorView {
  kind: ApiErrorKind;
  code: string;
  message: string;
  status?: number;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string };
  detail?: unknown;
}

function getStatus(raw: unknown): number | null {
  if (typeof raw === 'object' && raw !== null && 'status' in raw) {
    const status = (raw as { status: unknown }).status;
    if (typeof status === 'number') return status;
  }
  return null;
}

function getData(raw: unknown): ErrorEnvelope | null {
  if (typeof raw === 'object' && raw !== null && 'data' in raw) {
    const data = (raw as { data: unknown }).data;
    if (typeof data === 'object' && data !== null) return data as ErrorEnvelope;
  }
  return null;
}

function envelopeCode(data: ErrorEnvelope | null): string | null {
  return data?.error?.code ?? null;
}

function envelopeMessage(data: ErrorEnvelope | null): string | null {
  if (data?.error?.message) return data.error.message;
  if (typeof data?.detail === 'string' && data.detail) return data.detail;
  return null;
}

export function toApiError(raw: unknown): ApiErrorView {
  if (raw instanceof TypeError) {
    return {
      kind: 'network',
      code: 'NETWORK_ERROR',
      message: 'Could not reach the server. Check your connection and try again.',
    };
  }

  const status = getStatus(raw);
  const data = getData(raw);

  if (status === 401) {
    return {
      kind: 'auth',
      code: envelopeCode(data) ?? 'UNAUTHORIZED',
      message: 'Your session has expired. Sign in again to continue.',
      status,
    };
  }

  if (status === 403) {
    return {
      kind: 'auth',
      code: envelopeCode(data) ?? 'FORBIDDEN',
      message: 'Your account does not have permission to perform this action.',
      status,
    };
  }

  if (status === 404) {
    if (envelopeCode(data) === 'NOT_FOUND') {
      return {
        kind: 'not_found',
        code: 'NOT_FOUND',
        message: envelopeMessage(data) ?? 'The requested resource does not exist.',
        status,
      };
    }
    return {
      kind: 'unavailable',
      code: 'ENDPOINT_UNAVAILABLE',
      message:
        envelopeMessage(data) ??
        'This server does not expose the requested endpoint yet.',
      status,
    };
  }

  if (status !== null && status >= 500) {
    return {
      kind: 'server',
      code: envelopeCode(data) ?? 'SERVER_ERROR',
      message: envelopeMessage(data) ?? 'The server failed to complete the request.',
      status,
    };
  }

  if (status !== null) {
    return {
      kind: 'unknown',
      code: envelopeCode(data) ?? 'REQUEST_FAILED',
      message: envelopeMessage(data) ?? `The request failed (${status}).`,
      status,
    };
  }

  if (raw instanceof Error) {
    return { kind: 'network', code: 'NETWORK_ERROR', message: raw.message };
  }

  return {
    kind: 'unknown',
    code: 'REQUEST_FAILED',
    message: 'The request failed for an unknown reason.',
  };
}

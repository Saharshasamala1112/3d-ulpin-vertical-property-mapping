/**
 * Typed error contract for the GEOSIX API (Feature 12).
 *
 * The backend standardizes only a subset of statuses onto the envelope
 * `{ error_code, message, details }` (verified: 404, 409, 422, 500). Other
 * statuses such as 400/401/403 still return the legacy `{ detail }` body, so
 * every error must be normalized rather than assumed to be standardized.
 *
 * Verified backend behavior worth preserving here:
 *  - 422 VALIDATION_ERROR flattens pydantic `loc` into `details` keys, e.g.
 *    `details["area_sqm"]`.
 *  - model-level validators collapse to `details["request"]` rather than an axis
 *    field, so callers must treat `request` as a form-level error.
 *  - malformed GeoJSON content is NOT caught by schema validation and surfaces
 *    as an opaque 500 INTERNAL_ERROR, so it cannot be mapped to a field.
 */

export type ApiErrorDetails = Record<string, unknown>;

/** Detail key the backend uses for model-level (non-field) validation errors. */
export const FORM_LEVEL_DETAIL_KEY = 'request';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Coerce an arbitrary `details` value into a displayable string. */
function toDisplayString(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return 'Invalid value';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/**
 * Normalize the many shapes a `details` value can take into a flat
 * field-name -> message map.
 */
export function extractFieldErrors(details: ApiErrorDetails | undefined): Record<string, string> {
  const result: Record<string, string> = {};
  if (!details) return result;

  for (const [key, value] of Object.entries(details)) {
    if (key === FORM_LEVEL_DETAIL_KEY) continue;

    if (Array.isArray(value)) {
      const messages = value.map(toDisplayString).filter(Boolean);
      if (messages.length) result[key] = messages.join(' ');
      continue;
    }
    if (isRecord(value)) {
      // Nested pydantic loc such as { "geometry": { "coordinates": "..." } }.
      for (const [nestedKey, nestedValue] of Object.entries(value)) {
        result[nestedKey] = toDisplayString(nestedValue);
      }
      continue;
    }
    result[key] = toDisplayString(value);
  }

  return result;
}

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly details: ApiErrorDetails;
  /** Flattened field-name -> message map, excluding the form-level key. */
  readonly fieldErrors: Record<string, string>;
  /** Raw response payload, retained for diagnostics and unmapped cases. */
  readonly payload: unknown;

  constructor(options: {
    status: number;
    errorCode: string;
    message: string;
    details?: ApiErrorDetails;
    payload?: unknown;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.errorCode = options.errorCode;
    this.details = options.details ?? {};
    this.fieldErrors = extractFieldErrors(this.details);
    this.payload = options.payload;
  }

  get isValidationError(): boolean {
    return this.status === 422 || this.errorCode === 'VALIDATION_ERROR';
  }

  get isNotFound(): boolean {
    return this.status === 404 || this.errorCode === 'NOT_FOUND';
  }

  get isConflict(): boolean {
    return this.status === 409 || this.errorCode === 'CONFLICT';
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }

  /** Form-level error text, e.g. a model-level `details["request"]` message. */
  get formError(): string | undefined {
    const formLevel = this.details[FORM_LEVEL_DETAIL_KEY];
    if (formLevel === undefined) return undefined;
    return toDisplayString(formLevel);
  }

  /** Field-level message for `field`, if the server attributed one to it. */
  fieldError(field: string): string | undefined {
    return this.fieldErrors[field];
  }

  /**
   * Best single message for banners: prefer a form-level detail, then the
   * envelope message.
   */
  get displayMessage(): string {
    return this.formError ?? this.message;
  }

  /**
   * Build an `ApiError` from any backend error payload.
   *
   * Handles the Feature 12 envelope first, then the legacy `{ detail }` body
   * (string or object, including the older `{ detail: { error: { code, message } } }`
   * nesting), and finally falls back to a status-derived default.
   */
  static fromPayload(status: number, payload: unknown): ApiError {
    if (isRecord(payload)) {
      if (typeof payload.error_code === 'string') {
        return new ApiError({
          status,
          errorCode: payload.error_code,
          message:
            typeof payload.message === 'string' ? payload.message : defaultMessage(status),
          details: isRecord(payload.details) ? payload.details : {},
          payload,
        });
      }

      if ('detail' in payload) {
        return fromLegacyDetail(status, payload.detail, payload);
      }
    }

    return new ApiError({
      status,
      errorCode: defaultCode(status),
      message: defaultMessage(status),
      payload,
    });
  }
}

function fromLegacyDetail(status: number, detail: unknown, payload: unknown): ApiError {
  // Defensive: older handlers nested a standardized body under detail.error.
  if (isRecord(detail) && isRecord(detail.error)) {
    const nested = detail.error;
    return new ApiError({
      status,
      errorCode: typeof nested.code === 'string' ? nested.code : defaultCode(status),
      message: typeof nested.message === 'string' ? nested.message : defaultMessage(status),
      details: isRecord(nested.details) ? nested.details : {},
      payload,
    });
  }

  return new ApiError({
    status,
    errorCode: defaultCode(status),
    message: toDisplayString(detail),
    payload,
  });
}

function defaultCode(status: number): string {
  if (status === 404) return 'NOT_FOUND';
  if (status === 409) return 'CONFLICT';
  if (status === 422) return 'VALIDATION_ERROR';
  if (status >= 500) return 'INTERNAL_ERROR';
  return `HTTP_${status}`;
}

function defaultMessage(status: number): string {
  if (status === 404) return 'Resource not found';
  if (status === 409) return 'Conflict';
  if (status === 422) return 'Request validation failed';
  if (status === 401) return 'Unauthorized';
  if (status === 403) return 'Forbidden';
  if (status >= 500) return 'Internal server error';
  return `Request failed with status ${status}`;
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/**
 * Narrow an unknown thrown value to an `ApiError`, or wrap it so callers never
 * have to deal with raw `TypeError`s from the transport layer.
 */
export function toApiError(value: unknown): ApiError {
  if (isApiError(value)) return value;
  if (value instanceof Error) {
    return new ApiError({
      status: 0,
      errorCode: 'NETWORK_ERROR',
      message: value.message || 'Network request failed',
    });
  }
  return new ApiError({
    status: 0,
    errorCode: 'NETWORK_ERROR',
    message: 'Network request failed',
  });
}

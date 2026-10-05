import { ApiError, toApiError } from './api-error';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

/** Statuses that must never be parsed as JSON. */
const NO_CONTENT_STATUSES = new Set([204, 205]);

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getAccessToken(): string | null {
    return localStorage.getItem('geosix-access-token');
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem('geosix-refresh-token');
  }

  private buildHeaders(customHeaders?: HeadersInit): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(customHeaders as Record<string, string> | undefined),
    };

    const token = this.getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  /**
   * Read a response body without assuming it is JSON.
   *
   * 204/205 responses and empty 200 bodies return `undefined` rather than
   * throwing, which is what previously made every DELETE fail with
   * "Unexpected end of JSON input".
   */
  private static async parseBody<T>(response: Response): Promise<T> {
    if (NO_CONTENT_STATUSES.has(response.status)) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      return text as unknown as T;
    }
  }

  private static async readError(response: Response): Promise<ApiError> {
    const payload = await ApiClient.parseBody<unknown>(response).catch(() => null);
    return ApiError.fromPayload(response.status, payload ?? null);
  }

  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: customHeaders, ...rest } = options;
    const headers = this.buildHeaders(customHeaders);
    const serialized = body === undefined ? undefined : JSON.stringify(body);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...rest,
        headers,
        body: serialized,
      });

      if (response.status === 401 && this.getRefreshToken()) {
        const refreshed = await this.tryRefresh();
        if (refreshed) {
          const retryHeaders = this.buildHeaders(customHeaders);
          const retryResponse = await fetch(`${this.baseUrl}${endpoint}`, {
            ...rest,
            headers: retryHeaders,
            body: serialized,
          });

          if (!retryResponse.ok) {
            throw await ApiClient.readError(retryResponse);
          }
          // `parseBody` already maps 204/205 and empty bodies to `undefined`,
          // which is what the retried request path needs for DELETEs.
          return ApiClient.parseBody<T>(retryResponse);
        }
      }

      if (!response.ok) {
        throw await ApiClient.readError(response);
      }

      return await ApiClient.parseBody<T>(response);
    } catch (error) {
      // Normalize transport failures and unexpected payloads into ApiError so
      // callers only ever have to handle one error type.
      throw toApiError(error);
    }
  }

  private async tryRefresh(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) return false;

      const data = (await response.json()) as {
        access_token?: string;
        refresh_token?: string;
      };
      if (!data.access_token || !data.refresh_token) return false;

      localStorage.setItem('geosix-access-token', data.access_token);
      localStorage.setItem('geosix-refresh-token', data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'POST', body });
  }

  async put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'PUT', body });
  }

  async delete<T = void>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient(API_BASE);

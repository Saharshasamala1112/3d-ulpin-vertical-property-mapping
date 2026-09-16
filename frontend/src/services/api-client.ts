const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

class ApiClient {
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

  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: customHeaders, ...rest } = options;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(customHeaders as Record<string, string>),
    };

    const token = this.getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...rest,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && token) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.getAccessToken()}`;
        const retryResponse = await fetch(`${this.baseUrl}${endpoint}`, {
          ...rest,
          headers,
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!retryResponse.ok) {
          const error = await retryResponse.json().catch(() => null);
          throw { status: retryResponse.status, data: error };
        }
        return retryResponse.json();
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw { status: response.status, data: error };
    }

    return response.json();
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

      const data = await response.json();
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

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient(API_BASE);

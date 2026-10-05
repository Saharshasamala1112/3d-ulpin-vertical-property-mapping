import { apiClient } from './api-client';
import type {
  AuthTokens,
  LoginRequest,
  PasswordResetConfirm,
  RegisterRequest,
  User,
} from '../types';

export const authService = {
  async login(data: LoginRequest): Promise<AuthTokens> {
    return apiClient.post<AuthTokens>('/api/v1/auth/login', data);
  },

  async register(data: RegisterRequest): Promise<User> {
    return apiClient.post<User>('/api/v1/auth/register', data);
  },

  async getMe(): Promise<User> {
    return apiClient.get<User>('/api/v1/auth/me');
  },

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/api/v1/auth/forgot-password', { email });
  },

  async resetPassword(data: PasswordResetConfirm): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/api/v1/auth/reset-password', data);
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v1/auth/logout');
    } finally {
      this.clearTokens();
    }
  },

  setTokens(tokens: AuthTokens): void {
    localStorage.setItem('geosix-access-token', tokens.access_token);
    localStorage.setItem('geosix-refresh-token', tokens.refresh_token);
  },

  clearTokens(): void {
    localStorage.removeItem('geosix-access-token');
    localStorage.removeItem('geosix-refresh-token');
  },

  hasToken(): boolean {
    return !!localStorage.getItem('geosix-access-token');
  },
};

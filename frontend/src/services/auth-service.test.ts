import { describe, it, expect, beforeEach, vi } from 'vitest';
import { authService } from './auth-service';

// Mock apiClient
vi.mock('./api-client', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { apiClient } from './api-client';

const mockPost = vi.mocked(apiClient.post);
const mockGet = vi.mocked(apiClient.get);

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('login calls apiClient.post with correct endpoint and data', async () => {
    const tokens = { access_token: 'at', refresh_token: 'rt', token_type: 'bearer' };
    mockPost.mockResolvedValueOnce(tokens);

    const result = await authService.login({ email: 'a@b.com', password: 'pass' });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/login', { email: 'a@b.com', password: 'pass' });
    expect(result).toEqual(tokens);
  });

  it('register calls apiClient.post with correct data', async () => {
    const user = { id: '1', email: 'a@b.com', full_name: 'Test', is_active: true, created_at: '', updated_at: '' };
    mockPost.mockResolvedValueOnce(user);

    const result = await authService.register({ email: 'a@b.com', password: 'pass1234', full_name: 'Test' });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/register', { email: 'a@b.com', password: 'pass1234', full_name: 'Test' });
    expect(result).toEqual(user);
  });

  it('setTokens stores tokens in localStorage', () => {
    authService.setTokens({ access_token: 'at', refresh_token: 'rt', token_type: 'bearer' });
    expect(localStorage.getItem('geosix-access-token')).toBe('at');
    expect(localStorage.getItem('geosix-refresh-token')).toBe('rt');
  });

  it('clearTokens removes tokens from localStorage', () => {
    localStorage.setItem('geosix-access-token', 'at');
    localStorage.setItem('geosix-refresh-token', 'rt');
    authService.clearTokens();
    expect(localStorage.getItem('geosix-access-token')).toBeNull();
    expect(localStorage.getItem('geosix-refresh-token')).toBeNull();
  });

  it('hasToken returns true when token exists', () => {
    localStorage.setItem('geosix-access-token', 'at');
    expect(authService.hasToken()).toBe(true);
  });

  it('hasToken returns false when no token', () => {
    expect(authService.hasToken()).toBe(false);
  });

  it('getMe calls apiClient.get with correct endpoint', async () => {
    const user = { id: '1', email: 'a@b.com', full_name: 'Test', is_active: true, created_at: '', updated_at: '' };
    mockGet.mockResolvedValueOnce(user);

    const result = await authService.getMe();

    expect(mockGet).toHaveBeenCalledWith('/api/v1/auth/me');
    expect(result).toEqual(user);
  });
});

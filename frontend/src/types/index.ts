export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
  updated_at: string;
}

export type UserRole = 'reader' | 'editor' | 'admin';

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

/**
 * Re-exported so consumers can `import type { ApiError } from '../types'`.
 *
 * The previous interface here modelled a legacy `{ error: { code, message } }`
 * body that the API no longer returns for standardized statuses. The real
 * contract is a class carrying the HTTP status alongside the Feature 12
 * envelope. See `src/services/api-error.ts`.
 */
export { ApiError, isApiError, toApiError } from '../services/api-error';

export interface HealthResponse {
  status: string;
  service: string;
}

export type Theme = 'light' | 'dark';

# GEOSIX Authentication

## Overview

JWT-based authentication with access and refresh tokens.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create new user account |
| POST | `/api/v1/auth/login` | Get access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Exchange refresh token for new tokens |
| POST | `/api/v1/auth/logout` | Invalidate session |
| GET | `/api/v1/auth/me` | Get current user profile |
| POST | `/api/v1/auth/forgot-password` | Request password reset |

## Token Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | (dev default) | Signing secret — **change in production** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |

## Frontend Token Storage

Tokens are stored in localStorage behind the auth service abstraction:

- `geosix-access-token` — Current access token
- `geosix-refresh-token` — Current refresh token

To change storage mechanism, update `auth-service.ts`.

## Security Notes

- Passwords are hashed with bcrypt (never stored plaintext)
- JWT secrets must be set via environment variables
- The development default secret is NOT secure for production
- Never log passwords or tokens
- Never expose password hashes in API responses

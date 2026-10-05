# GEOSIX Authentication and Authorization

## Overview

GEOSIX uses JWT access and refresh tokens. Every cadastral data endpoint requires
an authenticated, active user. Access tokens identify the user on each request;
the user's role is loaded from the database so role changes take effect without
waiting for a new token.

## Public and protected routes

| Method | Path | Access |
|--------|------|--------|
| GET | `/api/v1/health`, `/api/health` | Public health checks |
| GET | `/api/v1`, `/docs`, `/redoc`, `/openapi.json` | Public API metadata and documentation |
| POST | `/api/v1/auth/register` | Public; new accounts receive the `reader` role |
| POST | `/api/v1/auth/login` | Public; protected by per-email and per-IP throttling |
| POST | `/api/v1/auth/refresh` | Public route; requires a valid refresh token |
| POST | `/api/v1/auth/forgot-password` | Public; accepts `{ "email": "..." }` and never reveals account existence |
| POST | `/api/v1/auth/reset-password` | Public; requires a valid, single-use reset token |
| POST | `/api/v1/auth/logout` | Authenticated |
| GET | `/api/v1/auth/me` | Authenticated |
| GET | `/api/v1/auth/users` | Admin |
| PATCH | `/api/v1/auth/users/{user_id}/role` | Admin |
| GET | `/api/v1/parcels/**`, `/api/v1/buildings/**`, `/api/v1/floors/**`, `/api/v1/units/**`, `/api/v1/units/{unit_id}/geometry` | Reader or higher |
| POST, PUT, PATCH | Cadastral and geometry writes | Editor or higher |
| DELETE | Parcel, building, floor, and unit endpoints | Admin |
| POST | `/api/v1/vdc/**`, `/api/v1/topology/**` | Editor or higher |
| POST | `/api/v1/units/{unit_id}/vdc` | Editor or higher |
| PUT | `/api/v1/units/{unit_id}/geometry` | Editor or higher |

All routes not listed as public require an access token. Future routers must
apply `require_reader` at the router level, then use `require_editor` for
mutations and `require_admin` for destructive or user-management operations.
This keeps authentication explicit even for POST endpoints that run validation
or generation workflows.

## Permission matrix

| Role | Read cadastral data | Create or update data | Delete data | Manage users and roles |
|------|---------------------|-----------------------|-------------|------------------------|
| `reader` | Yes | No (`403`) | No (`403`) | No (`403`) |
| `editor` | Yes | Yes | No (`403`) | No (`403`) |
| `admin` | Yes | Yes | Yes | Yes |

New accounts are always `reader`. An administrator can list users with
`GET /api/v1/auth/users` and assign roles with
`PATCH /api/v1/auth/users/{user_id}/role`, sending `{ "role": "reader" }`,
`{ "role": "editor" }`, or `{ "role": "admin" }`.

API-created and API-updated cadastral rows record the acting user's UUID in
`created_by` and `updated_by`. These audit identifiers intentionally have no
foreign-key constraint so the audit history remains after an account is removed.

## Password recovery

1. Submit `POST /api/v1/auth/forgot-password` with a JSON body containing the
   account email. The response is the same whether or not that account exists.
2. When SMTP is configured and the account exists, GEOSIX emails a link to the
   frontend reset page. Only a SHA-256 digest of the random token is stored.
3. Submit the token and a new password to
   `POST /api/v1/auth/reset-password`. Tokens expire after the configured
   interval and can be consumed only once.

Without SMTP configuration, the request endpoint still returns the generic
response and logs that delivery is disabled; configure SMTP before enabling
password recovery in a deployed environment.

## Login throttling

Failed logins are counted independently for normalized email addresses and
client IP addresses in the database-backed `login_attempts` table. After
`LOGIN_MAX_ATTEMPTS` failures, a key is locked for
`LOGIN_LOCKOUT_MINUTES`. The state survives application restarts and expires
automatically; a successful login clears both relevant counters.

## Token and email configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | Development-only value in debug mode | Unique secret of at least 32 characters when `DEBUG=false` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed attempts allowed before lockout |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lockout duration |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Password-reset token lifetime |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | Base URL included in reset emails |
| `SMTP_HOST` | Empty | SMTP server; empty disables email dispatch |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | Empty | Optional SMTP username |
| `SMTP_PASSWORD` | Empty | Optional SMTP password |
| `SMTP_FROM` | `no-reply@geosix.local` | Sender address |
| `SMTP_STARTTLS` | `true` | Upgrade the SMTP connection with STARTTLS |

## Frontend token storage

Tokens are stored in localStorage behind the auth service abstraction:

- `geosix-access-token` — current access token
- `geosix-refresh-token` — current refresh token

The shared API client attaches the access token, refreshes and retries once on
`401` when possible, and normalizes both `401` and `403` responses for UI
feedback. A `403` indicates insufficient permission; it is not treated as an
expired session.

## Security notes

- Passwords are hashed with bcrypt and are never stored as plaintext.
- Reset tokens are random, hashed at rest, expiring, and single-use.
- Never log passwords, access tokens, refresh tokens, or reset tokens.
- The development JWT secret is not suitable for production.
- Already-issued JWTs remain valid until their normal expiry; immediate session
  revocation is out of scope.

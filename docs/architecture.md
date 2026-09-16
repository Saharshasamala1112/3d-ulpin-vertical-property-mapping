# GEOSIX Architecture

## Overview

GEOSIX is a layered vertical-cadastre engine for 3D ULPIN generation and volumetric property governance.

## Directory Structure

```
geosix/
├── frontend/          # React + TypeScript + Vite
├── backend/           # Python + FastAPI
├── docs/              # Project documentation
├── ai-geospatial/     # AI/geospatial processing (future)
└── 3d-visualization/  # 3D rendering (future)
```

## Backend

- **Framework:** FastAPI (Python 3.11+)
- **Authentication:** JWT-based (access + refresh tokens)
- **Password Hashing:** bcrypt via passlib
- **Configuration:** pydantic-settings (environment variables)
- **API Prefix:** `/api/v1`

### Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Application factory, middleware, router registration |
| `app/core/config.py` | Environment-based settings |
| `app/core/security.py` | JWT and password utilities |
| `app/core/dependencies.py` | FastAPI dependency injection (current user) |
| `app/api/v1/auth.py` | Authentication endpoints |
| `app/api/v1/health.py` | Health check endpoint |
| `app/models/user.py` | User model (in-memory for dev) |
| `app/schemas/auth.py` | Pydantic request/response schemas |

### Adding New Endpoints

1. Create router in `app/api/v1/your_module.py`
2. Include in `app/main.py`: `app.include_router(your.router, prefix="/api/v1/...")`
3. Add OpenAPI tags in `create_app()`

## Frontend

- **Framework:** React 19 + TypeScript
- **Build Tool:** Vite
- **Routing:** React Router v7
- **State:** React Context (auth, theme)

### Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Root component with providers and routes |
| `src/app/AuthContext.tsx` | Authentication state and actions |
| `src/app/ThemeContext.tsx` | Theme state (light/dark) |
| `src/services/api-client.ts` | Centralized HTTP client |
| `src/services/auth-service.ts` | Authentication API calls |
| `src/styles/globals.css` | Design tokens and base styles |

### Adding New Pages

1. Create page in `src/pages/app/YourPage.tsx`
2. Add route in `src/App.tsx` under the `/app` layout
3. Add nav item in `src/components/layout/Sidebar.tsx`

### Adding New Services

1. Create `src/services/your-service.ts`
2. Import and use `apiClient` from `./api-client`
3. Follow existing patterns in `auth-service.ts`

## Theme System

Design tokens are defined in `src/styles/globals.css` using CSS custom properties.

- Light theme: `:root` and `[data-theme="light"]`
- Dark theme: `[data-theme="dark"]`

Toggle via `useTheme()` hook. Theme persists in localStorage.

## Authentication Flow

1. User submits credentials to `/api/v1/auth/login`
2. Backend returns access + refresh tokens
3. Frontend stores tokens in localStorage (behind auth service)
4. API client attaches access token to requests
5. On 401, API client attempts refresh before failing
6. Logout clears tokens and resets auth state

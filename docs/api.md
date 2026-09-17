# GEOSIX API

## Base URL

```
http://localhost:8000
```

## Documentation

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## API Prefix

All endpoints are under `/api/v1`.

## Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/health` | No | Service health check |
| GET | `/api/v1` | No | API version metadata |

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login` | No | Get tokens |
| POST | `/api/v1/auth/refresh` | No | Refresh tokens |
| POST | `/api/v1/auth/logout` | Yes | Logout |
| GET | `/api/v1/auth/me` | Yes | Current user |
| POST | `/api/v1/auth/forgot-password` | No | Request reset |

## Error Format

```json
{
  "detail": {
    "error": {
      "code": "ERROR_CODE",
      "message": "Human-readable message"
    }
  }
}
```

## Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request identifier |
| `X-Response-Time` | Server response time |
| `Authorization` | `Bearer <token>` for authenticated requests |

## Adding New Endpoints

1. Create router file in `backend/app/api/v1/`
2. Define endpoints with Pydantic schemas
3. Register router in `backend/app/main.py`
4. Add OpenAPI tags for organization

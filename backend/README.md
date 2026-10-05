# GEOSIX Backend

## Configuration and Environment

Settings are defined once in `app/core/config.py` as a Pydantic `Settings` model and are read from, in increasing order of precedence: built-in defaults, the variables in the process environment, then `backend/.env`. A single instance is created at import time as `app.core.config.settings` and imported from there by the rest of the application, so there is exactly one source of configuration.

The repository ships `backend/.env.example` as a template of every supported variable, with example values only. Copy it to `backend/.env` for local work:

```sh
cd backend
cp .env.example .env
```

`.env` holds credentials in the clear and must stay untracked. Do not commit it, and prefer a secret manager for anything shared.

### Configuration variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_NAME`, `APP_VERSION` | Application identity, reported in responses and logs. | `GEOSIX API`, `0.1.0` |
| `DEBUG` | Enables debug behaviour and the development secret fallback. | `true` |
| `CORS_ORIGINS` | JSON list of browser origins allowed to call the API. | `["http://localhost:5173"]` |
| `DATABASE_URL` | SQLAlchemy URL for the application database. | local `geosix_dev` |
| `TEST_DATABASE_URL` | Disposable database used by the integration suite only. | local `geosix_test` |
| `JWT_SECRET_KEY` | HMAC signing key for access and refresh tokens. | none (see below) |
| `JWT_ALGORITHM` | Signing algorithm for issued tokens. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime. | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime. | `7` |
| `BCRYPT_ROUNDS` | Password hashing cost factor. | `12` |

`TEST_DATABASE_URL` is read by the integration tests, not by the application settings model.

### JWT signing secret

`JWT_SECRET_KEY` has no usable default. It is validated while `Settings` is being constructed, which happens when `app.core.config` is imported — before the database engine in `app/core/database.py` and the ASGI app in `app/main.py` are created. A non-debug configuration that cannot sign tokens safely therefore fails at startup, rather than at the first login attempt.

In production (`DEBUG=false`) the settings refuse to build when the secret:

- is missing or empty, including a value that is only whitespace;
- is a known placeholder, such as the development secret from `.env.example` or the `change-me-in-production-use-a-real-secret` value that older revisions shipped as a default;
- is shorter than **32 characters**.

The error names `JWT_SECRET_KEY`, states the minimum length, and shows the generation command. There is no override: weakening or bypassing the check is not supported, so fix the configuration instead.

Generate a secret per environment:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a different value for development, staging and production, and supply it through your secret manager.

### Local development

`DEBUG=true` keeps the documented development path available. When `JWT_SECRET_KEY` is unset, the settings fall back to the insecure value `geosix-insecure-development-only-secret`, which is what `.env.example` ships. This makes `uvicorn app.main:app` work from a fresh clone with no secret handling at all.

That fallback is scoped to `DEBUG=true` and carries no production guarantee. The same value is rejected outright when `DEBUG=false`, so it cannot be carried into a deployment by accident. A developer-supplied `JWT_SECRET_KEY` is always used as-is and is never overwritten.

### Production checklist

Set `DEBUG=false` and supply, through your deployment platform's secret store: a unique `JWT_SECRET_KEY` of at least 32 characters, the production `DATABASE_URL`, an accurate `CORS_ORIGINS` list, and the intended `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` / `BCRYPT_ROUNDS` values. Leave `BCRYPT_ROUNDS` at `12`; the test suite lowers it only to keep runs fast.

## ORM and Migration Schema Policy

Alembic migrations define the PostgreSQL/PostGIS schema and are the source of truth. Keep SQLAlchemy mappings aligned to migrated columns, types, nullability, defaults, enum labels, constraints, foreign keys, and indexes; do not change migration history merely to accommodate ORM drift.

Python enums persist their `.value` strings as native PostgreSQL enum labels. Keep each SQLAlchemy enum's `values_callable` aligned with the labels declared in its migration.

Timestamp columns are `NOT NULL` without database defaults in the migrations. ORM models therefore use timezone-aware UTC client defaults for inserts and client-side `onupdate` values for updates; do not add server defaults to the mappings unless the migrations also define them.

The live schema contract compares `Base.metadata` with SQLAlchemy inspection of the configured PostgreSQL database, including columns, types, defaults, constraints, indexes, foreign keys, and enum labels. It also verifies timestamp-only ORM inserts and enum round trips. Run it against a migrated test database:

```sh
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/geosix_test'
pytest -q tests/integration/test_schema_contract.py
```
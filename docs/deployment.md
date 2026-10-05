# GEOSIX Deployment

## Purpose

This document is the repeatable deployment path for GEOSIX. It covers two things:

1. **One command up.** `docker compose up --build` starts the whole stack — PostGIS,
   the FastAPI backend, and the frontend nginx — on a machine that has nothing
   installed but Docker.
2. **A documented production path.** How the same images are configured for a real
   deployment: explicit origins, a real signing secret, migrations run deliberately
   rather than at boot, and a backup/restore procedure that does not depend on
   copying raw Docker volume files.

Everything asserted here about configuration comes from
[`backend/app/core/config.py`](../backend/app/core/config.py) and
[`docker-compose.yml`](../docker-compose.yml). Where this document and the code
disagree, the code is correct and this document is a bug.

Related documents: [authentication.md](authentication.md) for the JWT/RBAC contract,
[development.md](development.md) for the branching and merge-request workflow,
[architecture.md](architecture.md) for the code layout.

## Architecture

```
                        host
                          |
                  :8080 (FRONTEND_PORT)
                          |
                 +--------v---------+
                 |    frontend      |   nginxinc/nginx-unprivileged
                 |     (nginx)      |   non-root, serves the Vite bundle
                 +---+----------+---+
                     |          |
      /              |          |  GET /api/v1/...
  browser  --------- +          + ------------------> +------------------+
                     |  SPA                           |     backend     |
                     |  history                       |  uvicorn :8000  |
                     |  fallback                      |  non-root, 2 wrk|
                     +----------o--------------------+  +--------+-----+
                                |                             |
                     +----------v--------------+              |
                     |        postgres         |   SELECT 1  |
                     |  postgis/postgis:16-3.4 | <------------+
                     |   geosix_postgres_data   |              |
                     +-------------------------+         +----v-----+
                                                       | alembic  |
                                                       | upgrade  |
                                                       +----------+
```

Request paths that matter:

| Path | Meaning |
|------|---------|
| `http://localhost:8080/` | The SPA. Served by frontend nginx. |
| `http://localhost:8080/api/v1/...` | Proxied by frontend nginx to `backend:8000`. |
| `http://localhost:8080/api/health` | Same, for the legacy health route. |
| `http://127.0.0.1:8000/docs` | Backend directly, loopback only, for local debugging. |

The browser **never** learns the `backend` hostname. `backend` resolves only inside
the Compose network, so pointing the browser at `http://backend:8000` would simply
fail to resolve. `api-client.ts` uses the relative base (`VITE_API_BASE_URL` unset →
`API_BASE = ''`), so the browser calls its own origin and nginx forwards `/api/`.

That is also why the frontend image is environment independent: it is built once and
works on any host, because the only hostname it knows is the Docker service name,
which Compose supplies.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker Engine | 24+ | Compose v2 (`docker compose`, not `docker-compose`) |
| Docker Compose | v2.20+ | Required for `depends_on: condition: service_healthy` and `develop`/`watch` syntax used here |
| Host RAM | ~2 GB free | The frontend build stage compiles the three.js bundle; the runtime images are small |
| Host disk | ~3 GB | Node build cache, Python wheels, and the PostGIS volume |
| `curl` | any | Only for `scripts/smoke-test.sh` |

No Python, Node, or database client is needed on the host. Docker-in-Docker is not
required either.

Not covered here: DNS, certificate issuance, firewall policy, and any
infrastructure-as-code. Those are the deployment target's responsibility.

## Environment configuration

Three files, three scopes. Do not duplicate a variable across them.

### Root `.env` — everything Compose needs

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_DB` | `geosix_dev` | Database name created by the PostGIS image |
| `POSTGRES_USER` | `geosix` | Database role |
| `POSTGRES_PASSWORD` | `geosix_password` | Database password. **Override in production.** |
| `POSTGRES_PORT` | `5432` | Host port for PostgreSQL (loopback only) |
| `BACKEND_PORT` | `8000` | Host port for the backend (loopback only) |
| `FRONTEND_PORT` | `8080` | Host port for nginx. Set `5173` if you prefer the Vite port |
| `DEBUG` | `true` | **Set `false` in production.** |
| `JWT_SECRET_KEY` | development-only value | **Replace in production.** See [JWT and security](#jwt-and-security) |
| `CORS_ORIGINS` | `["http://localhost:8080"]` | JSON list. Set the real frontend origin in production |
| `APP_NAME` | `GEOSIX API` | Shown in OpenAPI and `/api/v1` |
| `APP_VERSION` | `0.1.0` | Shown in OpenAPI and `/api/v1` |
| `API_V1_PREFIX` | `/api/v1` | API prefix |
| `FRONTEND_BASE_URL` | `http://localhost:8080` | Base URL used in password-reset emails |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `BCRYPT_ROUNDS` | `12` | bcrypt cost. Do not lower |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failures before lockout |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lockout duration |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Reset token lifetime |
| `SMTP_HOST` | empty | Empty disables reset-email dispatch |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | empty | SMTP username |
| `SMTP_PASSWORD` | empty | SMTP password |
| `SMTP_FROM` | `no-reply@geosix.local` | Envelope sender |
| `SMTP_STARTTLS` | `true` | Upgrade the connection with STARTTLS |

Copy the template and edit:

```bash
cp .env.example .env
```

`.env` is gitignored. It is the only place a secret belongs.

### `backend/.env` — running the app directly from a checkout

Used by `uvicorn app.main:app --reload` and by `alembic`. Holds the same
`Settings` variables listed above plus `TEST_DATABASE_URL`, which is only read by
`backend/tests/integration/conftest.py` and is never needed in a deployed image.

It is **not** used inside the containers: nothing is copied into either image, and
Compose passes configuration through the process environment instead. See
[Secret handling](#secret-handling).

### `frontend/.env` — running the Vite dev server

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | empty | Leave empty to use the Vite `/api` dev proxy (target `http://localhost:8000`) |

Never set this for a container build. It is a *build-time* variable that Vite
inlines into the JavaScript bundle, so setting it would bind the image to one
backend hostname. The Docker build leaves it unset.

### Which values are which

| | Development | Compose local deployment | Production |
|---|---|---|---|
| `DEBUG` | `true` | `true` (default) | **`false`** |
| `JWT_SECRET_KEY` | development value | development value | **unique, ≥32 chars** |
| `DATABASE_URL` | `…@localhost:5432/geosix_dev` | `…@postgres:5432/geosix_dev` | real connection string, injected as a secret |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | `["http://localhost:8080"]` | the real frontend origin(s) |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | `http://localhost:8080` | the real frontend origin |
| `SMTP_HOST` | empty | empty | the real SMTP host, or empty to disable resets |

## Local development

The original workflow, unchanged. Fast iteration with file watching and no image
build:

```bash
# Terminal 1 — database only
docker compose up -d postgres

# Terminal 2 — backend with reload
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # DATABASE_URL already points at localhost:5432
alembic upgrade head
uvicorn app.main:app --reload

# Terminal 3 — frontend with HMR
cd frontend
npm install
npm run dev
```

Frontend on <http://localhost:5173>. The Vite dev server proxies `/api` to
`localhost:8000` (`frontend/vite.config.ts`), so the browser again uses a relative
path and no CORS preflight happens. `5173` is in the default `CORS_ORIGINS`, which
is why the direct `localhost:8000` route works too.

This workflow is untouched by the container deployment. The one thing to know: the
container frontend binds `8080`, not `5173`, so both can run at the same time.

## Full Compose deployment

```bash
cp .env.example .env          # optional: the defaults work as-is
docker compose up --build
```

That builds both images and starts all three services. Startup order is enforced:
`postgres` must be `healthy` before `backend` starts, and `backend` must be
`healthy` before `frontend` starts.

Then apply migrations once (see [Migrations](#migrations)):

```bash
docker compose exec backend alembic upgrade head
```

Verify:

```bash
docker compose ps
curl -fsS http://localhost:8080/api/v1/health
curl -fsS http://localhost:8080/login      # SPA deep link
open http://localhost:8080
```

Or run the whole thing as a check:

```bash
./scripts/smoke-test.sh
```

Stop without touching data:

```bash
docker compose down
```

### Overriding the startup command

The image's `CMD` is production Uvicorn: no `--reload`, `--host 0.0.0.0`,
`--workers 2`. To tune it, add a `docker-compose.override.yml`:

```yaml
services:
  backend:
    command: >
      uvicorn app.main:app --host 0.0.0.0 --port 8000
      --workers 4 --proxy-headers --forward-allow-ips *
```

`--proxy-headers` matters only behind an external TLS terminator; see
[Reverse proxy and TLS](#reverse-proxy-and-tls).

## Database-only Compose usage

The database-only path still works and is still a first-class workflow — it is what
the local-development instructions above use, and what CI's integration suite is
modelled on.

```bash
docker compose up -d postgres
```

```bash
docker compose up -d postgres && docker compose exec postgres pg_isready -U geosix -d geosix_dev
```

`postgres` is the only service with no `depends_on`, so naming it starts it alone.
This is deliberately a **service-targeted** command rather than a Compose profile:
the acceptance requirement is that plain `docker compose up` brings up the full
stack, and putting `backend`/`frontend` behind a profile would silently reduce that
to Postgres.

To run backend and frontend against a database you started separately, that is
already the default behaviour — both depend on the `postgres` service and Compose
starts it if it is not running.

## Production checklist

- [ ] `DEBUG=false`
- [ ] `JWT_SECRET_KEY` generated per environment, ≥32 characters, not the development value
      (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] `POSTGRES_PASSWORD` and `DATABASE_URL` supplied by a secret manager, not in `.env` on disk
- [ ] `CORS_ORIGINS` lists the real frontend origin(s) — never `*`, never a wildcard subdomain
- [ ] `FRONTEND_BASE_URL` is the real frontend origin, so reset emails point somewhere reachable
- [ ] `BCRYPT_ROUNDS=12`
- [ ] `SMTP_HOST` configured (or reset-password explicitly understood to be non-functional)
- [ ] `alembic upgrade head` applied and verified before traffic is routed
- [ ] TLS terminated in front of nginx, and `http://` redirected to `https://`
- [ ] `POSTGRES_PORT` and `BACKEND_PORT` published only if needed, still bound to loopback
- [ ] Backup scheduled and **a restore rehearsed on a scratch database**
- [ ] `./scripts/smoke-test.sh` run against a production-shaped `.env` before going live
- [ ] `docker compose config` reviewed for any leftover development default

## Backend configuration

`backend/app/core/config.py` declares exactly these `Settings` fields. Compose
passes every one of them through the environment, so nothing silently falls back to
a code default.

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `APP_NAME` | str | `GEOSIX API` | OpenAPI title, `/api/v1` response |
| `APP_VERSION` | str | `0.1.0` | OpenAPI version, `/api/v1` response |
| `DEBUG` | bool | `true` | `false` in production; gates the secret rules below |
| `API_V1_PREFIX` | str | `/api/v1` | Informational; the routers in `app/main.py` hardcode the prefix |
| `CORS_ORIGINS` | list[str] | `["http://localhost:5173"]` | JSON list. See [CORS](#cors) |
| `JWT_SECRET_KEY` | str | `""` | See [JWT and security](#jwt-and-security) |
| `JWT_ALGORITHM` | str | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | |
| `DATABASE_URL` | str | `postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_dev` | SQLAlchemy URL; `postgresql+psycopg` selects the psycopg 3 driver |
| `BCRYPT_ROUNDS` | int | `12` | Lowering it weakens password hashing |
| `LOGIN_MAX_ATTEMPTS` | int | `5` | Per-email and per-IP failure budget |
| `LOGIN_LOCKOUT_MINUTES` | int | `15` | |
| `PASSWORD_RESET_EXPIRE_MINUTES` | int | `30` | |
| `FRONTEND_BASE_URL` | str | `http://localhost:5173` | Base URL in reset emails |
| `SMTP_HOST` | str | `""` | Empty disables dispatch |
| `SMTP_PORT` | int | `587` | |
| `SMTP_USER` | str | `""` | |
| `SMTP_PASSWORD` | str | `""` | |
| `SMTP_FROM` | str | `no-reply@geosix.local` | |
| `SMTP_STARTTLS` | bool | `true` | |

`TEST_DATABASE_URL` also appears in `backend/.env.example` but is **not** a
`Settings` field. Only `backend/tests/integration/conftest.py` reads it, and the
integration suite skips when it is unset. Do not set it in a deployed image.

## Frontend configuration

| Variable | Build time? | Default | Notes |
|----------|-------------|---------|-------|
| `VITE_API_BASE_URL` | yes | unset | Relative base `''` in the container. Never set it for a Docker build |

There is no runtime frontend configuration. Everything Vite inlines is baked into
`/usr/share/nginx/html/assets/*.js` at image build time, which is why the image is
environment independent: the only server-side behaviour is nginx's `/api/` proxy,
and the only hostname in it is the Compose service name.

nginx reads no environment variables and holds no credentials.

## JWT and security

`Settings` validates the signing secret at construction time, before the database
engine or the ASGI app exist. With `DEBUG=false` it refuses to build unless:

- `JWT_SECRET_KEY` is set and non-blank;
- it is not on the denylist of known placeholders (`change-me`, `secret`,
  `your-secret-key`, and the documented development value, case-insensitively);
- it is at least 32 characters (`MIN_JWT_SECRET_LENGTH`).

With `DEBUG=true` an unset secret falls back to
`DEBUG_ONLY_JWT_SECRET_KEY = "geosix-insecure-development-only-secret"`, and that
same value is rejected the moment `DEBUG=false`. So the zero-setup Compose default
cannot silently become a production secret: flipping `DEBUG` to `false` without
supplying a real secret stops the backend with an explicit error naming the
variable and the minimum length.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Generate one per environment (development, staging, production). Never reuse, never
commit, never share between deployments: rotating it invalidates every issued token.

Also relevant:

- `BCRYPT_ROUNDS=12` in production. The test suite lowers it to 4 for speed; that
  never reaches a deployed configuration.
- Access tokens live 30 minutes, refresh tokens 7 days, by default.
- Login throttling is persisted in the `login_attempts` table, so it survives a
  restart and is not per-container.
- nginx forwards `X-Forwarded-For` so per-IP throttling sees the browser address,
  not nginx's.

## CORS

`CORSMiddleware` is configured with `allow_origins=settings.cors_origins`,
`allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.

Set the **browser-facing** origin, not a Docker hostname:

```dotenv
CORS_ORIGINS=["https://geosix.example.com"]
```

Because the frontend proxies `/api/` on its own origin, a correctly deployed
frontend needs **no** CORS allowance at all — same-origin requests never trigger a
preflight. `CORS_ORIGINS` exists for the cases that do need it: a separate API
origin, a native client, or the `npm run dev` workflow, where Vite serves on 5173
and the API on 8000.

Do not set `*`. It is incompatible with credentialed requests, and it would let any
site issue authenticated calls.

The health endpoint does **not** hardcode an origin. It used to send
`Access-Control-Allow-Origin: http://localhost:5173` unconditionally, which made a
production health check advertise a development origin. CORS is now decided solely
by the middleware; see `tests/test_deployment.py`.

## SMTP

`Settings` declares `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM`, and `SMTP_STARTTLS`. These are the only SMTP variables the application
reads, and Compose passes all six.

Behaviour: an empty `SMTP_HOST` disables dispatch. `POST /api/v1/auth/forgot-password`
still returns its generic anti-enumeration response and logs that delivery is
disabled, so local development and CI never need a mail server. That means **with
`SMTP_HOST` unset, password recovery does not work** — the endpoint succeeds and no
email arrives.

To enable it, set at least `SMTP_HOST` and `SMTP_PORT`, plus `SMTP_USER` /
`SMTP_PASSWORD` if the server requires authentication. `FRONTEND_BASE_URL` must
match the real frontend origin, or the emailed link will point at a host no user can
reach.

Mail is sent synchronously inside the request. For a high-traffic deployment, move it
to a queue — that is a code change, not a configuration one, and is out of scope here.

## Database and PostGIS

PostGIS 16 / 3.4, unchanged from the earlier database-only work:

```yaml
image: postgis/postgis:16-3.4
volumes:
  - geosix_postgres_data:/var/lib/postgresql/data
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
```

The named volume `geosix_postgres_data` persists across `docker compose down` and
across image rebuilds. Only `docker compose down -v` removes it, and this
repository's scripts never run that.

The backend's `DATABASE_URL` uses the Compose service name:

```
postgresql+psycopg://geosix:<password>@postgres:5432/geosix_dev
```

`postgres` is right and `localhost` is wrong: inside the backend container,
`localhost` is the backend container.

PostgreSQL is published on `127.0.0.1:5432` so it is reachable from the host but
not from the network. In production, prefer not publishing it at all.

Spatial data lives in PostGIS `geometry` columns (`parcels.geom`,
`units.property_geometry`, …). Keep PostGIS enabled before running migrations —
revision `0001_enable_postgis` creates the extension, so a fresh `alembic upgrade
head` on a plain PostgreSQL image is not supported.

## Reverse proxy and TLS

The Compose frontend already terminates HTTP and proxies `/api/`. In production,
put a TLS terminator in front of it. A generic nginx example, to adapt to your own
certificate paths:

```nginx
# /etc/nginx/conf.d/geosix.conf
upstream geosix_frontend {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    server_name geosix.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name geosix.example.com;

    ssl_certificate     /etc/letsencrypt/live/geosix.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/geosix.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 32m;

    location / {
        proxy_pass         http://geosix_frontend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Connection        "";
    }
}
```

Certificate and DNS provisioning are **not** implemented by this repository. The
block above is configuration to copy and adapt; obtaining and renewing the
certificate is the deployment target's job.

Because the front proxy adds another hop, enable Uvicorn's proxy-header handling so
`request.client.host` is the real client:

```yaml
# docker-compose.override.yml
services:
  backend:
    command: >
      uvicorn app.main:app --host 0.0.0.0 --port 8000
      --workers 2 --proxy-headers --forward-allow-ips *
```

`--forward-allow-ips *` is only safe while port 8000 is unreachable from anywhere
except your proxy. If you publish it more widely, name the proxy's address instead.

TLS between the outer proxy and the frontend nginx container is not configured. On a
single host, loopback is the trust boundary; across hosts, terminate TLS in the
container or on a private network segment.

## Health checks

| Endpoint | Used by | Cost |
|----------|---------|------|
| `GET /api/v1/health` | Backend `HEALTHCHECK`, Compose healthcheck, smoke test | No query |
| `GET /api/health` | Pre-existing route, kept for compatibility | No query |
| `GET /healthz` | Frontend container `HEALTHCHECK` | Local nginx `return 200`, never leaves the container |
| `GET /api/v1` | OpenAPI `/openapi.json`, `/docs` | No query |

Both backend health routes return `{"status": "ok", "service": "geosix-api"}` and are
public. Both are kept: `/api/health` predates the `/api/v1` prefix and is documented
in [authentication.md](authentication.md).

Neither performs a database query. Readiness is already gated by the database's own
`pg_isready` healthcheck, so a liveness probe that queried PostGIS would conflate two
different failures. The application *does* verify connectivity once in `lifespan`
(a single `SELECT 1`) before serving; a failure there means the container exits rather
than serving broken requests.

The backend's healthcheck is a stdlib-only probe, so no `curl` or `wget` is installed
in the image for it:

```bash
docker compose exec backend python -m app.core.healthcheck --url http://127.0.0.1:8000/api/v1/health
```

Check status manually:

```bash
docker compose ps
docker inspect --format '{{json .State.Health}}' geosix-backend | jq
```

## Smoke test

```bash
./scripts/smoke-test.sh
```

What it does, in order: checks prerequisites → `docker compose build` → `up -d` →
`alembic upgrade head` → waits for all three services healthy → verifies backend
health directly → verifies frontend SPA serving and React Router deep links →
verifies `browser → nginx → backend` through the frontend origin → verifies CORS is
not hardcoded → verifies containers are non-root and the backend image has no build
tooling. It exits non-zero on the first failure and dumps container logs for the
services involved.

```bash
./scripts/smoke-test.sh --no-build     # reuse existing images
./scripts/smoke-test.sh --teardown     # stop containers when done
./scripts/smoke-test.sh --timeout 300  # longer health wait
FRONTEND_PORT=9000 ./scripts/smoke-test.sh
SMOKE_NO_MIGRATE=1 ./scripts/smoke-test.sh   # re-test a live database
```

Cleanup: without `--teardown` the stack is left running for inspection. With
`--teardown` it runs `docker compose down`, which **preserves** the
`geosix_postgres_data` volume. The script never runs `down -v`, never removes a
volume, and never runs `docker system prune`.

No secrets are needed: it runs against the `.env.example` defaults. It uses only
public routes — health, root metadata, and an anonymous `GET /api/v1/auth/me`,
which must return `401` rather than `502`. That single check is what proves the
proxy reaches the backend's *authentication* layer, not just its static health route.
No test account is created.

## Migrations

Alembic is the only schema authority. `backend/alembic/env.py` reads
`settings.database_url`, so migrations target whatever `DATABASE_URL` says — the
container's value is `…@postgres:5432/…`.

```bash
# 1. Start the database and wait for it to be healthy
docker compose up -d postgres
until docker compose exec postgres pg_isready -U geosix -d geosix_dev; do sleep 1; done

# 2. Apply migrations (idempotent)
docker compose exec backend alembic upgrade head

# 3. Start or confirm the backend, then the frontend
docker compose up -d backend frontend

# 4. Verify
docker compose exec backend alembic current
curl -fsS http://localhost:8080/api/v1/health
```

`alembic upgrade head` is **not** part of the container entrypoint, on purpose. An
entrypoint that migrates on every boot would race with other replicas during a
rolling restart and would make it impossible to tell a schema failure from a
startup failure. Run it once, deliberately, as a deployment step.

For a one-off migration without starting the whole stack:

```bash
docker compose run --rm backend alembic upgrade head
```

Creating a revision (developer machine, never in production):

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
pytest          # integration tests skip unless TEST_DATABASE_URL is set
```

Do not hardcode a revision id in automation. `upgrade head` is the target;
`alembic history` shows where you are.

Round-trip check, against a disposable database:

```bash
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_test alembic upgrade head
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_test alembic downgrade -1
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_test alembic upgrade head
```

`downgrade` is destructive. Only run it against a database you are willing to lose —
never `geosix_dev` or a production database.

## Backup and restore

Use `pg_dump` / `pg_restore`. They capture the PostGIS extension, the `geometry`
columns, the `spatial_ref_sys` entries the app depends on, and the `alembic_version`
row, and they are consistent and version-aware. Copying files out of
`/var/lib/postgresql/data` is **not** a backup method: the files are only coherent
when PostgreSQL is shut down, and hand-assembling them will eventually produce a
restore that fails on `spatial_ref_sys`.

### Backup

```bash
mkdir -p backups

docker compose exec -T postgres \
  pg_dump --format=custom --compress=9 --no-owner --no-privileges \
    --username=geosix --dbname=geosix_dev \
  > "backups/geosix-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

`--format=custom` is required: it is the only format `pg_restore` accepts, and it
preserves geometry types and index definitions.

While the stack is up, a plain SQL dump is also usable:

```bash
docker compose exec -T postgres \
  pg_dump --format=plain --no-owner --no-privileges \
    --username=geosix --dbname=geosix_dev \
  > "backups/geosix-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

Record the schema revision alongside the dump, so a restore can be checked against
the code that produced it:

```bash
docker compose exec -T postgres \
  psql --username=geosix --dbname=geosix_dev \
  --tuples-only --no-align --command='SELECT version_num FROM alembic_version' \
  > "backups/revision-$(date -u +%Y%m%dT%H%M%SZ).txt"
```

### Restore

Into a new database first. Never restore over a database you still need:

```bash
docker compose exec -T postgres \
  createdb --username=geosix --owner=geosix geosix_restore

docker compose exec -T postgres \
  pg_restore --dbname=geosix_restore --no-owner --no-privileges --exit-on-error \
  < backups/geosix-YYYYMMDDTHHMMSSZ.dump

docker compose exec -T postgres \
  psql --username=geosix --dbname=geosix_restore \
  --command='SELECT PostGIS_Version()'
```

Restore into the live database: stop the backend first so nothing writes while the
restore runs, then bring it back.

```bash
docker compose stop backend frontend
# drop and recreate the target database if a full replace is intended, then:
docker compose exec -T postgres pg_restore --dbname=geosix_dev --no-owner --exit-on-error \
  < backups/geosix-YYYYMMDDTHHMMSSZ.dump
docker compose up -d backend frontend
docker compose exec backend alembic current
```

If the dump is older than the current code, run `alembic upgrade head` afterwards.

### Volume considerations

| Action | Effect on `geosix_postgres_data` |
|--------|----------------------------------|
| `docker compose down` | Volume preserved |
| `docker compose up --build` / image rebuild | Volume preserved |
| `docker compose down -v` | **Volume deleted** — do not run against data you need |
| `docker volume rm <name>` | **Volume deleted** |
| `docker system prune --volumes` | **Volume deleted** |

If you do copy volume files anyway, stop PostgreSQL first so the data directory is
coherent:

```bash
docker compose stop postgres
# only then copy /var/lib/postgresql/data out of the volume
docker compose start postgres
```

Treat that as a last resort, not a backup.

## Upgrade procedure

```bash
# 0. Back up first. See "Backup and restore".
# 1. Pull the new code
git fetch origin && git checkout <tag-or-branch>

# 2. Rebuild images (no `down`, so the volume and containers survive)
docker compose build

# 3. Apply migrations before the new code serves traffic
docker compose up -d postgres
docker compose exec backend alembic upgrade head

# 4. Recreate the application containers
docker compose up -d --force-recreate backend frontend

# 5. Verify
docker compose ps
./scripts/smoke-test.sh --no-build
```

Order matters: migrate, then serve. Starting new code against an older schema fails
on the first query that touches a new column, which is a worse failure than a brief
window where the old code meets the new schema.

Rollback is `alembic downgrade -1` **and** redeploying the previous image — the code
and the schema have to move together.

## Troubleshooting

**`JWT_SECRET_KEY is required when DEBUG is false`**
Expected. `DEBUG=false` with no real secret. Generate one and put it in `.env`.

**Backend restarts in a loop, logs show `OperationalError` at startup**
`lifespan` ran `SELECT 1` and failed: the database is unreachable or not migrated.
Check `docker compose logs backend` and `docker compose exec postgres pg_isready`.

**Frontend returns 502 on `/api/...`**
nginx cannot reach `backend`. Check `docker compose ps` (is `backend` healthy?) and
`docker compose logs frontend`. Also confirm nothing was published directly in a way
that bypasses nginx — the browser should only ever use the frontend origin.

**`localhost:5173` shows the app, but `/api/...` 502s in the container**
`FRONTEND_PORT` was set to `5173` while `npm run dev` holds that port, or the image
is stale. Check `docker compose config` for the resolved port.

**Direct navigation to `/app/parcels` returns 404**
SPA history fallback is not in effect, so nginx is not using
`frontend/nginx/default.conf`. Confirm the config file is mounted:
`docker compose exec frontend nginx -T | grep try_files`.

**`alembic upgrade head` fails with `extension "postgis" is not available`**
The database is plain PostgreSQL. Create the extension
(`CREATE EXTENSION postgis;`) or use the `postgis/postgis:16-3.4` image.

**CORS error in the browser console**
`CORS_ORIGINS` does not contain the browser's origin — the origin includes the port
and the scheme. Check the browser's exact `Origin` header. If you are on
`npm run dev`, `http://localhost:5173` must be present.

**Password reset succeeds but no email arrives**
`SMTP_HOST` is empty, which disables dispatch by design. Set the `SMTP_*` values.

**`docker compose up` says the port is already allocated**
Something holds 5432, 8000, or 8080. Change it in `.env`
(`POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`) and re-run `docker compose up -d`.

**Integration tests all skip**
`TEST_DATABASE_URL` is unset. Point it at a disposable migrated database; see
[Local development](#local-development) and the root `README.md`.

## Secret handling

Where a secret may live:

| Location | Allowed |
|----------|---------|
| `.env` on the deployment host, mode `0600` | Yes. Gitignored |
| Secret manager injected as environment variables | Yes, preferred |
| `docker-compose.yml` / `.env.example` as `${VAR:-local-default}` | Yes for local development values only |
| A Dockerfile `ENV` / `ARG` | **No** |
| An image layer, baked at build time | **No** |
| `.env` copied into an image | **No** |
| `docker-compose.yml` literal `password:` / `secret:` | **No** |
| Git, any branch | **No** |
| Command line (`docker run -e JWT_SECRET_KEY=...`) | Avoid; it is visible in `ps` and shell history |

Enforced by the repository:

- `backend/.dockerignore` and `frontend/.dockerignore` both exclude `.env` and
  `.env.*`, so a stray `COPY . .` cannot pick one up.
- No Dockerfile sets a credential via `ENV` or `ARG`. `backend/Dockerfile` does not
  mention `JWT_SECRET_KEY` or `SMTP_PASSWORD` at all.
- `docker-compose.yml` interpolates every credential-bearing variable; none is a
  bare literal.
- `backend/app/core/config.py` refuses to start with `DEBUG=false` and a weak,
  blank, or placeholder secret.
- `backend/tests/test_deployment.py` asserts all of the above, so a regression fails
  `pytest` rather than waiting to be noticed in production.

Verify by hand:

```bash
# No credential in any committed deployment artifact
grep -nE 'ENV (JWT_SECRET_KEY|SMTP_PASSWORD|POSTGRES_PASSWORD)|COPY .*\.env' \
  backend/Dockerfile frontend/Dockerfile

# No .env in any image layer
docker run --rm --entrypoint sh geosix-backend:local  -c 'ls -a /app'
docker run --rm --entrypoint sh geosix-frontend:local -c 'ls -a /usr/share/nginx/html'

# Resolved compose configuration shows only your local values
docker compose config | grep -E 'JWT_SECRET_KEY|POSTGRES_PASSWORD'
```

## Container hardening

Both images run as a dedicated non-root user, with no compiler, package installer,
or development tooling in the final stage.

| | Backend | Frontend |
|---|---|---|
| Runtime user | `geosix` (system, UID/GID 10001) | `nginx` (UID/GID 101) |
| Installed as | `/opt/venv` | — |
| Package manager | removed (`pip uninstall pip setuptools wheel`) | absent |
| Compiler | absent | absent |
| Dev dependencies | never installed (`pip install .`, not `.[dev]`) | never installed (`npm ci` installs `devDependencies` in the build stage only; the runtime stage copies just `dist/`) |
| Listening port | 8000 | 8080 |
| Healthcheck | stdlib probe (`python -m app.core.healthcheck`) | busybox `wget --spider` |

Verify:

```bash
docker compose exec backend  id      # uid=10001(geosix)
docker compose exec frontend id      # uid=101(nginx)
docker inspect --format '{{.Config.User}}' geosix-backend   # geosix
docker inspect --format '{{.Config.User}}' geosix-frontend  # nginx
```

Image inspection:

```bash
docker image inspect geosix-backend:local  --format '{{.Config.User}} {{.Config.ExposedPorts}}'
docker image inspect geosix-frontend:local --format '{{.Config.User}} {{.Config.ExposedPorts}}'
docker history --no-trunc geosix-backend:local | grep -iE 'secret|password'   # expect no match
```

Both `.dockerignore` files also keep `node_modules/`, `.venv/`, `dist/`, test
directories, coverage artifacts, and `*.egg-info/` out of the build context.

The frontend exposes no server-side secret: the bundle is static JavaScript, and the
only server configuration is nginx's `/api/` proxy. nginx serves
`/usr/share/nginx/html` and nothing else, denies dotfile requests, hides the version
header, and its paths are fixed rather than user-supplied.

## CI and image registry

**Registry push is explicitly deferred.** `.gitlab-ci.yml` builds no image and
pushes nothing to any registry.

Reasons, based on what the repository actually contains:

- There is no registry job, no image-push helper, and no reference to
  `CI_REGISTRY`/`CI_REGISTRY_IMAGE` anywhere in the pipeline today.
- No runner declares a docker-executor or dind service beyond what the existing
  jobs use, so there is no evidence of a runner with registry credentials.
- Nothing in the repository states which registry, namespace, or tag scheme a
  deployment consumes, so a push job would be guesswork that could publish an image
  to the wrong place.

Fabricating a push workflow on those foundations would be worse than deferring it.
When the registry and credentials are decided, add a `build` job using
`CI_REGISTRY_IMAGE` with the built-in `docker login -u "$CI_REGISTRY_USER" -p
"$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"`, restricted to tag pipelines:

```yaml
images:publish:
  stage: build
  image: docker:27-cli
  rules:
    - if: '$CI_COMMIT_TAG'
  script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
    - docker build -t "$CI_REGISTRY_IMAGE/backend:$CI_COMMIT_TAG" -f backend/Dockerfile backend
    - docker build -t "$CI_REGISTRY_IMAGE/frontend:$CI_COMMIT_TAG" -f frontend/Dockerfile frontend
    - docker push "$CI_REGISTRY_IMAGE/backend:$CI_COMMIT_TAG"
    - docker push "$CI_REGISTRY_IMAGE/frontend:$CI_COMMIT_TAG"
```

Tag-only rules matter: a job that pushes on every branch would publish images from
merge request pipelines. Store `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD` as
masked CI/CD variables, never in the repository.

The pipeline already covers the deployment artifacts:

| Job | What it proves |
|-----|----------------|
| `images:build` | Both images build on a docker-enabled runner, and are **not** published |
| `backend:test` | `alembic upgrade head` / `downgrade -1` / `upgrade head` work against real PostGIS 16-3.4 |
| `backend:build` | the sources compile |
| `frontend:build` | `npm run build` succeeds, including the geometry-viewer chunk budget |
| `backend:lint`, `frontend:lint` | style gates |
| `backend/tests/test_deployment.py` | the Dockerfiles, compose file, nginx config, and this document satisfy the invariants below, with no Docker daemon required |

`images:build` runs `docker compose config --quiet`, builds both images with
non-publishing tags, validates the nginx config with `nginx -t`, asserts neither
image runs as root, and — importantly — asserts that the backend image *refuses* to
start with `DEBUG=false` and the development JWT secret while *accepting* a strong
one. That last check is a real security regression gate, and it would have caught a
secret baked into an image.

What CI does **not** do: run `scripts/smoke-test.sh`. It needs a host Docker daemon
with published ports, which this pipeline does not currently provide, and it mutates
the running stack. Run it locally before opening a merge request:

```bash
docker compose config
docker compose build
./scripts/smoke-test.sh
```

## Local validation checklist

Run these before opening a merge request. They need only Docker and Python.

```bash
# Backend static checks and unit tests
cd backend
ruff check app tests alembic
ruff format --check app tests
pytest -q

# Integration suite against a disposable migrated database
docker compose up -d postgres
docker compose exec postgres createdb -U geosix -O geosix geosix_w41_test
docker compose exec postgres psql -U geosix -d geosix_w41_test -c 'CREATE EXTENSION postgis'
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_w41_test alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_w41_test pytest -q

# Migration round trip
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_w41_test alembic downgrade -1
DATABASE_URL=postgresql+psycopg://geosix:geosix_password@localhost:5432/geosix_w41_test alembic upgrade head

# Frontend
cd ../frontend
npm test
npm run lint
npm run build

# Deployment artifacts
cd ..
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker inspect --format '{{.Config.User}}' geosix-backend
docker inspect --format '{{.Config.User}}' geosix-frontend
./scripts/smoke-test.sh --no-build
docker compose down        # preserves the volume
```

Never point the destructive parts of that list at `geosix_dev` or any database you
care about.
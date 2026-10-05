# GEOSIX

A Layered Vertical-Cadastre Engine for 3D ULPIN Generation & Volumetric Property Governance

GEOSIX is organized as a multi-module platform for backend API services, frontend workflows, AI-powered geospatial analysis, and 3D spatial visualization. Existing application behavior is preserved while future workstreams receive dedicated repository areas.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API available at http://localhost:8000

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at http://localhost:5173

### Environment Variables

Copy `.env.example` to `.env` in both `backend/` and `frontend/`.

### Full stack with Docker Compose

`docker compose up --build` starts the whole stack — PostGIS, the FastAPI backend, and
an nginx-served frontend — with nothing installed but Docker. Migrate once, then open
<http://localhost:8080>:

```bash
cp .env.example .env            # optional; the defaults work as-is
docker compose up --build
docker compose exec backend alembic upgrade head
```

Verify with the smoke test, which builds, starts, waits for health, and checks the
`browser -> nginx -> backend` path:

```bash
./scripts/smoke-test.sh
```

Full deployment guidance — production configuration, CORS, secrets, migrations,
backup/restore, upgrades, and troubleshooting — is in
[docs/deployment.md](docs/deployment.md).

### Database-only PostgreSQL / PostGIS

The PostgreSQL 16 + PostGIS 3.4 service in [docker-compose.yml](docker-compose.yml)
also works on its own. It exposes PostgreSQL on `127.0.0.1:5432` and creates a
persistent named volume for local development. This is the usual starting point for
the workflow above.

```bash
docker compose config
docker compose up -d postgres
```

## Project Structure

```
geosix/
├── frontend/          React + TypeScript + Vite
├── backend/           Python + FastAPI
├── docs/              Documentation
├── ai-geospatial/     AI/geospatial processing (future)
└── 3d-visualization/  3D rendering (future)
```


The frontend retains its existing React, TypeScript, Vite, routing, authentication, and backend API integration behavior. The backend retains its FastAPI application and organized package structure.

## Testing

```bash
# Backend unit tests (no database required)
cd backend && pytest

# Frontend
cd frontend && npm test && npm run lint && npm run build

# Backend validation
python3 -m compileall backend/app
```

### Integration tests (PostgreSQL + PostGIS)

The suite in `backend/tests/integration/` runs against a **real** PostgreSQL/PostGIS
database. It is skipped automatically when `TEST_DATABASE_URL` is unset, so
`pytest` still works without a local PostGIS instance. To run it, point the variable
at a database you have migrated and are willing to have tests write to:

```bash
# 1. Start PostGIS (or use an existing instance)
docker compose up -d postgres

# 2. Create and migrate a dedicated test database
createdb geosix_test
export TEST_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@localhost:5432/geosix_test"
DATABASE_URL="$TEST_DATABASE_URL" alembic upgrade head

# 3. Run everything, including the integration suite
cd backend && pytest
```

You can also run only the integration tests:

```bash
cd backend && pytest tests/integration -m integration
```

Notes:

- Use a **dedicated throwaway database**. The tests deliberately exercise
  `DELETE` cascades and archive operations.
- Each test runs inside a transaction that is rolled back afterwards, so a run
  leaves no rows behind and tests are order-independent.
- Service-layer code calls `session.commit()`. The `db_session` fixture binds the
  session to a connection-level transaction using
  `join_transaction_mode="conditional_savepoint"`, so those commits release
  savepoints rather than persisting data. Do **not** call `rollback()` on the
  `db_session` fixture from a test: it deassociates the outer transaction and a
  later write would really commit. The fixture fails loudly if this happens.
- Bcrypt runs at `bcrypt_rounds = 12` in production; the test session lowers the
  live cost to 4 for speed and restores it afterwards.

### Coverage

The CI pipeline enforces a minimum of **80%** line coverage. Coverage is not
enabled by default because it adds roughly 9 seconds per run:

```bash
cd backend && pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

The `backend:test` job runs exactly that command against a `postgis/postgis`
service, migrates the database first, and publishes `coverage.xml` as a job
artifact. A drop below the threshold fails the pipeline.

The foundation also reserves [ai-geospatial/README.md](ai-geospatial/README.md), [3d-visualization/README.md](3d-visualization/README.md), and [docs/README.md](docs/README.md) for future workstreams and shared documentation.

## License

Proprietary — GEOSIX Project

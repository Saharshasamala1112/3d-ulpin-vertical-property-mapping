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

### PostgreSQL / PostGIS foundation

The repository includes a PostgreSQL 16 + PostGIS 3.4 foundation in [docker-compose.yml](docker-compose.yml). It exposes PostgreSQL on port 5432 and creates a persistent named volume for local development.

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
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test && npm run lint && npm run build

# Backend validation
python3 -m compileall backend/app
```

The foundation also reserves [ai-geospatial/README.md](ai-geospatial/README.md), [3d-visualization/README.md](3d-visualization/README.md), and [docs/README.md](docs/README.md) for future workstreams and shared documentation.

## License

Proprietary — GEOSIX Project

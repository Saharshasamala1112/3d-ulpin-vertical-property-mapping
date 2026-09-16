# GEOSIX

A Layered Vertical-Cadastre Engine for 3D ULPIN Generation & Volumetric Property Governance

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

## Project Structure

```
geosix/
├── frontend/          React + TypeScript + Vite
├── backend/           Python + FastAPI
├── docs/              Documentation
├── ai-geospatial/     AI/geospatial processing (future)
└── 3d-visualization/  3D rendering (future)
```

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm run build
```

## License

Proprietary — GEOSIX Project

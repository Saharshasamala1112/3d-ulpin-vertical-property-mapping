# 3D Visualization

Interactive 3D scene rendering and visual analysis for the GEOSIX platform.

The first implemented surface is a **unit-level property volume viewer** at
`/app/visualization`. It renders the axis-aligned bounding box that the
geometry service stores for each unit, so a registered property can be
explored as a stack of floors and units.

## What it renders

Each unit with persisted geometry is drawn as a box using its
`x_min/x_max`, `y_min/y_max` and `z_min/z_max` bounds, coloured by floor. The
scene is Z-up: `z_min`/`z_max` are heights and map directly onto three.js'
Z axis instead of being rotated into three's default Y-up.

Deliberate limitation: **building and parcel footprints are not drawn.**
Their `footprint_geometry` is GeoJSON in **SRID 4326 (degrees)**, whereas unit
AABBs are in the **local metric frame (metres)**. Mixing them would misplace
geometry by orders of magnitude. Supporting footprints properly needs a
reprojection step, which is not in scope here.

## Running it

Prerequisites: a PostGIS-enabled database with the schema migrated.

```bash
# 1. Database
cd backend
alembic upgrade head          # requires DATABASE_URL / TEST_DATABASE_URL

# 2. API on :8000
uvicorn app.main:app --reload

# 3. Frontend on :5173 (proxies /api to :8000)
cd ../frontend
npm install
npm run dev
```

Then open <http://localhost:5173/app/visualization>, sign in, and pick a
parcel and building. Buildings with no floors, or floors with no units, show
an explanatory empty state rather than an empty canvas.

## Controls

| Input | Action |
| --- | --- |
| Left drag | Orbit |
| Right / middle drag, or `Shift` + left drag | Pan |
| Scroll | Zoom |
| Hover a unit | Highlight and show its identifier |
| Click a unit | Select it and show full metrics in the side panel |
| Click a unit in the side list | Select and focus it in the scene |

## Data flow

The page walks the registry hierarchy and resolves geometry per unit:

```
GET /api/v1/parcels?page=1&per_page=100
GET /api/v1/parcels/{parcel_id}/buildings
GET /api/v1/buildings/{building_id}/floors
GET /api/v1/floors/{floor_id}/units
GET /api/v1/units/{unit_id}/geometry        (per unit)
```

Two consequences worth knowing:

- **Geometry lookups are N+1.** The service exposes only a single-unit
  endpoint, so a building with 200 units issues 200 requests. They are issued
  concurrently. A batch endpoint would remove this.
- **A 404 is normal, not an error.** A unit with no bounding box returns
  `404 NOT_FOUND`; those units are listed separately under
  "Without geometry" instead of failing the whole building.

The API returns `Numeric(18,6)` columns, which serialise as JSON **strings**.
`toUnitGeometry` in `frontend/src/types/geometry.ts` is the single place where
they become numbers. It rejects blank and non-numeric values rather than
letting `Number('')` silently produce `0`.

## Bundle budget

three.js plus `@react-three/fiber` is large, so the viewer is loaded lazily and
kept out of the initial bundle. `frontend/vite.config.ts` enforces a **1 MiB**
budget on the viewer chunk after every production build and fails the build if
it is exceeded:

```
[plugin enforce-chunk-budget] geometry-viewer chunk assets/GeometryViewer-*.js:
894.1 kB raw / 234.8 kB gzip (budget 1024.0 kB)
```

The budget is a guard against accidentally pulling in a heavy extra dependency
(for example `@react-three/drei`), not a limit on the three.js version. If the
check ever stops matching the chunk, the build **fails** rather than silently
skipping the check.

> Chunking is intentionally left to Vite. Forcing the chunk name via
> `manualChunks` makes Rolldown emit a `modulepreload` for it in `index.html`,
> which downloads ~900 kB on every page load and defeats the lazy import.

## Verifying

```bash
cd frontend
npm test          # vitest
npm run lint      # oxlint
npm run build     # tsc -b + vite build, including the chunk budget
```

Coverage: wire-format conversion and rejection of bad values, the geometry
service (hierarchy walking, 404 handling, error envelopes), the Z-up camera
maths, the floor palette, and the page's loading / empty / error / selection
states. The canvas itself needs a WebGL context that jsdom does not provide,
so `GeometryViewer` is mocked in the page tests and its camera behaviour is
covered through the extracted `orbit.ts` helpers.

## Files

| Path | Role |
| --- | --- |
| `frontend/src/pages/app/VisualizationPage.tsx` | Route body, selectors, unit list, selection |
| `frontend/src/components/visualization/GeometryViewer.tsx` | R3F canvas, boxes, edges, grid, input handling |
| `frontend/src/components/visualization/orbit.ts` | Pure Z-up camera maths (tested without WebGL) |
| `frontend/src/components/visualization/viewer-colors.ts` | Floor palette, shared with the page |
| `frontend/src/services/geometry-service.ts` | Registry traversal and scene assembly |
| `frontend/src/types/geometry.ts` | Wire and read models, the single string→number boundary |

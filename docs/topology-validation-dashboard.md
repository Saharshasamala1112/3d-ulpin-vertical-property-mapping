# Topology Validation Dashboard

Work item 37 (`[Feature] Implement Topology Validation Dashboard`, epic
`topology-validation`) adds the frontend surface for the read-only topology
validation API shipped in work item 25 ([topology-api.md](topology-api.md)).

## Route consolidation decision

Before this work item both `/app/topology` and `/app/validation` rendered the
same "module not available" placeholder from `ModulePages`, and the sidebar
listed two separate entries for one feature.

Decision:

- `/app/topology` is the canonical route and renders
  `frontend/src/pages/app/TopologyValidationPage.tsx`.
- `/app/validation` stays as a permanent redirect
  (`<Navigate to="/app/topology" replace />`) so bookmarks and older links keep
  working instead of falling through to the catch-all dashboard redirect.
- The sidebar has a single **Topology** entry pointing at `/app/topology`.
- `TopologyPage` and `ValidationPage` placeholders were removed from
  `frontend/src/pages/app/ModulePages.tsx`.

Rationale: the backend namespace, docs, and feature name are all
"topology validation"; keeping two routes would duplicate navigation and make
the 3D-view handoff target ambiguous.

## Run controls

The page owns a target picker (`ValidationTargetPicker`) with a scope toggle:

| Scope | Hierarchy required | Endpoint |
| --- | --- | --- |
| Whole building | parcel → building | `POST /api/v1/topology/validate/building/{building_id}` |
| Single unit | parcel → building → floor → unit | `POST /api/v1/topology/validate/unit/{unit_id}` |

Hierarchy lists come from `frontend/src/services/hierarchy-service.ts`
(`GET /api/v1/parcels`, `GET /api/v1/parcels/{id}/buildings`,
`GET /api/v1/buildings/{id}/floors`, `GET /api/v1/floors/{id}/units`).
The run button stays disabled until the selected scope has a complete target.

## Report rendering

`frontend/src/lib/validation-report.ts` normalises the
`TopologyValidationReport` payload into `ValidationIssue` rows:

| Category | Source field | Severity | Badge tone |
| --- | --- | --- | --- |
| Geometry validity | `geometry_errors` | `error` | danger |
| Volumetric overlap | `overlap_results` | `critical` | danger |
| Spatial gap | `gap_results` | `warning` | warning |
| Floor & elevation consistency | `elevation_errors` | `warning` | warning |

Rendering:

- **Pass/fail counts** — `ValidationSummaryCards` shows the overall
  `passed`/`failed` badge, total issue count, affected-unit count, and one
  count card per category using `summary.*_count`.
- **Expandable details** — `ValidationIssueSections` renders one collapsible
  section per category (`aria-expanded`, `aria-controls`); sections with
  findings start expanded. Every issue row carries its severity badge, code,
  human-readable message, affected unit IDs, and measured details (overlap
  volume and bounds, gap distance/direction and bounds, geometry field,
  elevation floor).
- **Severity styling** — Badge variants derived from the severity mapping
  above.
- **Affected unit navigation** — every affected unit ID links to
  `/app/units?unit=<unit_id>` (Feature 34 contract: the unit management UI
  reads the `unit` query parameter to focus one unit).

## 3D view status handoff (Feature 32 contract)

After each successful run the page derives a unit → status map and publishes it
through `frontend/src/lib/unit-validation-status.ts`:

```ts
interface UnitValidationStatusHandoff {
  generated_at: string;               // ISO-8601
  scope: 'building' | 'unit';
  target_id: string;                  // building_id or unit_id
  statuses: Record<string, 'valid' | 'overlap' | 'gap' | 'elevation' | 'geometry_error'>;
}
```

- Storage: `sessionStorage['geosix-unit-validation-status']` (JSON).
- Read/write helpers: `publishUnitValidationStatusHandoff`,
  `readUnitValidationStatusHandoff`, `clearUnitValidationStatusHandoff`.
- Building runs enrich the map with every unit of the building (via
  `hierarchyService.listBuildingUnitIds`) so healthy units are marked `valid`;
  if that enrichment fails, the map still contains all affected units.
- Status precedence per unit: `overlap` > `gap` > `elevation` >
  `geometry_error` > `valid`.
- Units that only appear in floor-level elevation errors (no `unit_id`) are
  reported as issues but are absent from the status map.

Feature 32 consumes the map as its colouring input; a missing or stale key
means "no validation data" and the view keeps its default styling.

## Loading, error, and empty states (Feature 12 contract)

`frontend/src/lib/api-error.ts` classifies the standard `{error: {code,
message}}` envelope thrown by `services/api-client.ts`:

| Situation | Kind | Presentation |
| --- | --- | --- |
| No run yet | — | Empty state: "No validation run yet" |
| Run in flight | — | Spinner card: "Running topology validation…" |
| 404 + `NOT_FOUND` | `not_found` | "Target not found" + backend message |
| 404 without envelope | `unavailable` | "Validation API not available" with a **Degraded** badge and a graceful-degradation note (other modules keep working) |
| 401/403 | `auth` | "Session expired" |
| 5xx | `server` | "Validation failed on the server" |
| fetch `TypeError` | `network` | "Cannot reach the server" |
| Passed report with zero issues | — | Summary cards + "All topology checks passed" |

Every error card exposes a **Retry** action that re-runs the same target.
Hierarchy fetch failures render inline beneath the picker selects.

## Design system and conventions

- Uses Feature 3 primitives only: `PageContainer`, `Card`, `Button`, `Badge`,
  `Input`-styled `Select` (new, mirrors `Input`), `EmptyState`, `LoadingSpinner`.
- No new framework or state library; React state + `react-router-dom` links.
- Styling is inline with the `globals.css` design tokens (light/dark aware).

## Verification

```bash
cd frontend
npm run lint          # oxlint
npm test              # vitest run
npm run build         # tsc -b && vite build
```

Component/behaviour tests:

- `src/pages/app/TopologyValidationPage.test.tsx` — idle, failed run with
  counts/expandable details/unit links, status handoff publication, passed run,
  unit scope, `not_found`, graceful degradation, network failure.
- `src/lib/validation-report.test.ts`, `src/lib/api-error.test.ts`,
  `src/lib/unit-validation-status.test.ts` — pure logic.
- `src/services/topology-service.test.ts`, `src/services/hierarchy-service.test.ts`
  — mocked API client.
- `src/components/ui/Select.test.tsx` — new design-system primitive.

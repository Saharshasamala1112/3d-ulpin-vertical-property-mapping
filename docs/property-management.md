# Property Management UI

Management screens for parcels, buildings, floors, and units, implemented
against the existing GEOSIX backend. This document covers how the UI behaves
and, importantly, where backend limitations shape that behaviour.

Source: `frontend/src/features/management/`

## Routes

| Route | Page | Scope |
| --- | --- | --- |
| `/app/parcels` | `ParcelPage` | All parcels |
| `/app/buildings` | `BuildingPage` | All buildings (filterable by parcel) |
| `/app/buildings/:parcelId` | `BuildingPage` | Buildings for one parcel |
| `/app/floors` | `FloorPage` | All floors (filterable by building) |
| `/app/floors/:buildingId` | `FloorPage` | Floors for one building |
| `/app/units` | `UnitPage` | All units (filterable by floor) |
| `/app/units/:floorId` | `UnitPage` | Units for one floor |

Every page is lazy-loaded in `frontend/src/App.tsx`, and each of the four form
dialogs is lazy-loaded from its page. The production build emits one chunk per
dialog, verified with `npm run build`.

## Create and update

Each entity has a create and an edit dialog. Edits send a **partial payload**
containing only changed fields, so a save never clobbers fields the user did
not touch.

Partial payloads are built with `json-diff`-based comparison in
`shared/json-diff.ts`. That comparison is **order-insensitive for object keys**
while remaining order-sensitive for arrays. This matters for GeoJSON: a
geometry whose keys were reordered, or metadata whose keys were reordered, is
correctly detected as unchanged and omitted from the update body.

The same treatment is applied to parcel `geometry`, parcel `metadata`, and
building `footprint_geometry`.

## Delete and archive semantics

These differ per entity and follow the backend exactly:

- **Parcel** — `DELETE` sets `status: "archived"`. It does not cascade, and
  archived parcels are not hidden automatically; the status filter shows them.
- **Unit** — `DELETE` sets `status: "archived"`. The row remains visible.
- **Building** — `DELETE` hard-deletes and cascades to its floors, which in
  turn cascade to their units.
- **Floor** — `DELETE` hard-deletes and cascades to its units. There is no
  child-count guard.

The UI never presents a soft delete as a hard delete, and never warns about a
cascade that will not happen.

## Counts

Building floor counts and floor unit counts are **opt-in**. The count columns
are hidden by default and populated by a "Show floor counts" / "Show unit
counts" toggle, which fetches the full child list and counts client-side. A
failed count request shows the cell as unknown rather than `0`, so a network
error is not misreported as "no children".

### Known limitation: no building-wide unit total

The API exposes no building-wide unit count and no endpoint to aggregate units
across a building's floors. Deriving one in the browser would require listing
every floor of the building and then listing units for each floor — 1+N requests
per building, and unbounded as the building grows.

This is therefore **not implemented**, and per-floor unit counts remain the
deepest available level. A building-wide total requires a backend endpoint or
count field.

## Search

Parcel search filters the **currently loaded page only**. The parcels endpoint
accepts `page`, `per_page`, `status`, and a lon/lat `bbox`, but no text-search
parameter. The UI states this explicitly in the empty state
("No parcels on this page match your search") rather than implying a
server-side search.

## Bounding boxes: the form is stricter than the server

Unit forms require each minimum to be **strictly less** than its maximum
(`min < max`). The API currently accepts `min <= max`, so a unit with an
inverted or degenerate-but-equal axis is rejected by the UI but would be
accepted by the backend. The form says so on screen.

This is a deliberate UI choice, not a bug. Aligning the form with the server
would mean accepting zero-height/zero-width volumes.

## Geometry validation

GeoJSON is validated structurally in `shared/geojson.ts`:

- Known geometry types (Point, MultiPoint, LineString, MultiLineString,
  Polygon, MultiPolygon) are checked recursively for correct nesting depth and
  finite numeric positions.
- Mixed-depth geometry is rejected — this is the common failure when pasting
  geometry from another tool.
- Any other geometry type is accepted as long as it carries an array
  `coordinates`, because the API stores geometry as an untyped JSON object and
  cannot be expected to police it.
- **`GeometryCollection` is not supported.** It nests `geometries` rather than
  `coordinates`, so it fails the "must include a coordinates property" check.
  Flatten it to a `MultiPolygon` or `MultiLineString` before entering it.
  This is a known UI limitation, not a server restriction.
- Every geometry, known or not, must carry a `coordinates` array.

The building footprint is the one place where the API is looser still:
`footprint_geometry` is typed `dict[str, Any]` and the backend explicitly
documents that "deep geometry validation is out of scope". The form therefore
accepts any structurally valid GeoJSON rather than restricting the footprint to
`Polygon`/`MultiPolygon`, matching what the server will actually store.

## ULPIN

The parcel form reads and writes `properties.ulpin` directly. It never calls
`/api/v1/parcels/{id}/ulpin`; the dedicated UL-pin fetch endpoint is not needed
for display or editing, and calling it would add a request per parcel.

## VDC

`/app/vdc` is still a placeholder. Unit rows display the stored `vdc_code` and
link to that route, but the optional per-unit VDC endpoint is not used for
navigation, since the stored value is already on the unit record.

## Authorization

The management backend routes are currently **unauthenticated**, even though
the platform has JWT support. The UI adds no client-side role gating for these
screens, because any such gating would be cosmetic and would not match the
server's actual behavior. If the routes are later protected, client-side gating
will need to be added to match.

## Error handling

`frontend/src/services/api-error.ts` normalizes failures into a single
`ApiError` type, supporting:

- Feature 12 errors (`{error_code, message, details}`)
- 422 field-level errors, keyed by payload field name
- `details["request"]`, collapsed to a form-level message
- Legacy FastAPI errors (`{detail: ...}`), which may be a string or a list

Server 422 field errors are mapped back onto the specific controls. One
translation is deliberate: the parcel API reports the payload key `geometry`
while the form control is `geometryText`, so that message is re-pointed at the
visible control instead of being dropped.

When a list request fails and there are no rows, the empty state is suppressed
so the page does not simultaneously claim "nothing here" and show an error.

All list responses are paginated, and list data is preserved across refresh so a
failed reload does not blank the table.

## Test coverage

`npx vitest run` covers, per entity: service contract, client validation and
partial-update construction, page behavior (filters, counts, cascades,
archive, deep links, error states), and form-dialog payload construction. The
dialog tests assert the exact request body, which is what catches payload-shape
regressions — a class of bug that unit tests on the validation helpers alone
cannot detect.

`frontend/src/services/api-client.test.ts` covers body serialization, empty and
non-JSON responses, both error payload shapes, transport failures, and the
401-refresh-retry path.

## Verification

```sh
cd frontend
npx tsc -b        # typecheck (stricter than bare `tsc --noEmit`)
npx vitest run    # 28 files, 262 tests
npx oxlint        # warnings only, exit 0
npm run build     # typecheck + production bundle
```

Note that `npx tsc --noEmit` is **not** equivalent to `npx tsc -b`: the project
references build (`tsconfig.app.json`) with `noUnusedLocals`,
`noUnusedParameters`, and `erasableSyntaxOnly` enabled, and it is what `npm run
build` runs. Use `tsc -b` when verifying changes.

import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useTheme } from '../../app/ThemeContext';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { PageContainer } from '../../components/layout/PageContainer';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Card';
import { Card } from '../../components/ui/Card';
import type { ParcelOption, BuildingOption, SceneUnit, BuildingScene } from '../../types/geometry';
import { floorColor } from '../../components/visualization/viewer-colors';
import { IndiaMap } from '../../components/visualization/IndiaMap';

/**
 * three.js and the viewer live in a separate chunk that is only fetched once
 * there is a scene to draw.
 */
const GeometryViewer = lazy(() => import('../../components/visualization/GeometryViewer'));

type Status = 'idle' | 'loading' | 'ready' | 'error';

const METRES = 'm';

function format(value: number, digits = 2): string {
  return value.toFixed(digits);
}

interface SelectProps {
  id: string;
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
}

function Select({ id, label, value, disabled, onChange, options, placeholder }: SelectProps) {
  return (
    <label htmlFor={id} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', minWidth: '200px' }}>
      <span style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--muted)' }}>{label}</span>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        style={{
          padding: '0.5rem 0.75rem',
          borderRadius: '6px',
          border: '1px solid var(--input-border)',
          background: 'var(--input-bg)',
          color: 'var(--foreground)',
          fontSize: '0.875rem',
        }}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function UnitDetails({ unit }: { unit: SceneUnit }) {
  const { dimensions, centroid, volume, bounds } = unit.geometry;
  const rows: [string, string][] = [
    ['Dimensions', `${format(dimensions.x)} x ${format(dimensions.y)} x ${format(dimensions.z)} ${METRES}`],
    ['Min corner', `${format(bounds.min.x)}, ${format(bounds.min.y)}, ${format(bounds.min.z)}`],
    ['Max corner', `${format(bounds.max.x)}, ${format(bounds.max.y)}, ${format(bounds.max.z)}`],
    ['Centroid', `${format(centroid.x, 3)}, ${format(centroid.y, 3)}, ${format(centroid.z, 3)}`],
    ['Volume', `${format(volume, 3)} m³`],
    ['Type', unit.unitType],
  ];

  return (
    <div data-testid="unit-details" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>{unit.unitIdentifier}</h3>
        <Badge variant="info">{unit.floor.levelName || `Floor ${unit.floor.floorNumber}`}</Badge>
        <Badge variant={unit.status === 'active' ? 'success' : 'default'}> {unit.status}</Badge>
      </div>
      <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.25rem 1rem', margin: 0, fontSize: '0.8125rem' }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: 'contents' }}>
            <dt style={{ color: 'var(--muted)' }}>{label}</dt>
            <dd style={{ margin: 0, fontVariantNumeric: 'tabular-nums' }}>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function VisualizationPage() {
  const { theme } = useTheme();

  const [parcels, setParcels] = useState<ParcelOption[]>([]);
  const [parcelId, setParcelId] = useState('');
  const [buildings, setBuildings] = useState<BuildingOption[]>([]);
  const [buildingId, setBuildingId] = useState('');
  const [scene, setScene] = useState<BuildingScene | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState('');

  // Selected parcel/building for map integration
  const [selectedParcel, setSelectedParcel] = useState<ParcelOption | null>(null);
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingOption | null>(null);

  useEffect(() => {
    let cancelled = false;
    import('../../services/geometry-service')
      .then((mod) => {
        if (cancelled) return;
        mod.listParcels()
          .then((result) => {
            if (cancelled) return;
            setParcels(result);
            if (result.length === 1) setParcelId(result[0].id);
          })
          .catch((cause) => {
            if (!cancelled) {
              setStatus('error');
              setError('Could not load parcels.');
            }
          });
      })
      .catch(() => {
        if (cancelled) return;
        setStatus('error');
        setError('Could not load parcels.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!parcelId) {
      setBuildings([]);
      setBuildingId('');
      setSelectedParcel(null);
      setSelectedBuilding(null);
      return;
    }
    let cancelled = false;
    import('../../services/geometry-service')
      .then((mod) => {
        if (cancelled) return;
        mod.listBuildings(parcelId)
          .then((result) => {
            if (cancelled) return;
            setBuildings(result);
            setStatus('idle');
          })
          .catch((cause) => {
            if (!cancelled) {
              setStatus('error');
              setError('Could not load buildings for this parcel.');
            }
          });
      })
      .catch(() => {
        if (cancelled) return;
        setBuildings([]);
        setStatus('error');
        setError('Could not load buildings for this parcel.');
      });
    return () => {
      cancelled = true;
    };
  }, [parcelId]);

  const onSelectBuilding = useCallback((id: string) => {
    setBuildingId(id);
    setScene(null);
    setSelectedUnitId(null);
    setError('');
    // Also update the selected building state for map
    const building = buildings.find((b) => b.id === id);
    if (building) setSelectedBuilding(building);
  }, [buildings]);

  useEffect(() => {
    if (!buildingId) {
      setStatus('idle');
      return;
    }
    const building = buildings.find((item) => item.id === buildingId);
    if (!building) return;

    let cancelled = false;
    import('../../services/geometry-service')
      .then((mod) => {
        if (cancelled) return;
        mod.loadBuildingScene(building)
          .then((result) => {
            if (cancelled) return;
            setScene(result);
            // Select first unit if available
            if (result.units.length > 0) {
              setSelectedUnitId(result.units[0].id);
            }
            setStatus('ready');
          })
          .catch((cause) => {
            if (!cancelled) {
              setStatus('error');
              setError('Could not load 3D geometry for this building.');
            }
          });
      })
      .catch(() => {
        if (cancelled) return;
        setStatus('error');
        setError('Could not load 3D geometry for this building.');
      });
    return () => {
      cancelled = true;
    };
  }, [buildingId, buildings]);

  const selectedUnit = useMemo(
    () => scene?.units.find((unit) => unit.id === selectedUnitId) ?? null,
    [scene, selectedUnitId],
  );

  const floorLegend = useMemo(() => {
    if (!scene) return [];
    const counts = new Map<string, { label: string; count: number; order: number }>();
    for (const unit of scene.units) {
      const existing = counts.get(unit.floor.id);
      const label = unit.floor.levelName || `Floor ${unit.floor.floorNumber}`;
      if (existing) existing.count += 1;
      else counts.set(unit.floor.id, { label, count: 1, order: scene.floors.findIndex((f) => f.id === unit.floor.id) });
    }
    return [...counts.entries()]
      .sort((a, b) => a[1].order - b[1].order)
      .map(([floorId, entry]) => ({ floorId, ...entry }));
  }, [scene]);

  return (
    <PageContainer
      title="3D Visualization"
      description="Inspect persisted unit geometry for a building"
      actions={
        status === 'error' ? (
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Reload
          </Button>
        ) : undefined
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* India Map Section */}
        <Card padding="1rem">
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <IndiaMap
              parcels={parcels}
              onParcelSelect={(parcel) => {
                setSelectedParcel(parcel);
                setParcelId(parcel?.id ?? '');
                setBuildings([]);
                setBuildingId('');
                setScene(null);
                setSelectedUnitId(null);
                setSelectedBuilding(null);
              }}
              onBuildingSelect={(building) => {
                setSelectedBuilding(building);
                // Find the parcel this building belongs to and select it
                const parcel = parcels.find((p) => p.ulpin === building.identifier);
                if (parcel) {
                  setSelectedParcel(parcel);
                  setParcelId(parcel.id);
                }
              }}
            />
            <Select
              id="parcel-select"
              label="Parcel"
              value={parcelId}
              disabled={parcels.length === 0}
              onChange={(value) => {
                setParcelId(value);
                setBuildingId('');
                setScene(null);
                setSelectedUnitId(null);
                setSelectedParcel(null);
                setSelectedBuilding(null);
              }}
              options={parcels.map((parcel) => ({ value: parcel.id, label: `${parcel.identifier} · ${parcel.ulpin}` }))}
              placeholder={parcels.length === 0 ? 'No parcels available' : 'Select a parcel'}
            />
            <Select
              id="building-select"
              label="Building"
              value={buildingId}
              disabled={buildings.length === 0 || status === 'loading'}
              onChange={onSelectBuilding}
              options={buildings.map((building) => ({ value: building.id, label: building.name || building.identifier }))}
              placeholder={buildings.length === 0 ? 'No buildings' : 'Select a building'}
            />
            <p style={{ fontSize: '0.75rem', color: 'var(--muted)', flex: '1 1 240px', minWidth: '200px' }}>
              Drag to orbit, shift-drag to pan, scroll to zoom. Vertical axis is height (Z).
            </p>
          </div>
        </Card>

        {status === 'loading' && (
          <Card>
            <LoadingSpinner />
            <p style={{ textAlign: 'center', fontSize: '0.875rem', color: 'var(--muted)' }}>
              Loading geometry…
            </p>
          </Card>
        )}

        {status === 'error' && (
          <Card>
            <EmptyState
              icon="⚠"
              title="Could not load the 3D model"
              description={error}
              action={
                <Button variant="secondary" onClick={() => window.location.reload()}>
                  Retry
                </Button>
              }
            />
          </Card>
        )}

        {status === 'idle' && (
          <Card>
            <EmptyState
              icon="◈"
              title="Choose a building"
              description="Select a parcel and building to render its unit geometry in 3D."
            />
          </Card>
        )}

        {status === 'ready' && scene && (
          <>
            {scene.units.length === 0 ? (
              <Card>
                <EmptyState
                  icon="⬜"
                  title="No unit geometry yet"
                  description={
                    scene.unitsWithoutGeometry.length > 0
                      ? `All ${scene.unitsWithoutGeometry.length} units in this building have no persisted bounding box. Publish geometry via PUT /api/v1/units/{unitId}/geometry to see them here.`
                      : 'This building has no units.'
                  }
                />
              </Card>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(260px, 1fr)', gap: '1rem' }}>
                <Card padding="0" style={{ overflow: 'hidden' }}>
                  <div style={{ height: '520px', width: '100%' }}>
                    <Suspense
                      fallback={
                        <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>
                          <LoadingSpinner size={32} />
                        </div>
                      }
                    >
                      <GeometryViewer
                        units={scene.units}
                        selectedId={selectedUnitId}
                        palette={theme}
                        onSelect={setSelectedUnitId}
                      />
                    </Suspense>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      gap: '1rem',
                      flexWrap: 'wrap',
                      padding: '0.75rem 1rem',
                      borderTop: '1px solid var(--border)',
                    }}
                  >
                    {floorLegend.map((entry) => (
                      <span
                        key={entry.floorId}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem' }}
                      >
                        <span
                          aria-hidden="true"
                          style={{ width: '12px', height: '12px', borderRadius: '3px', background: floorColor(entry.order) }}
                        />
                        {entry.label}
                        <span style={{ color: 'var(--muted)' }}>({entry.count})</span>
                      </span>
                    ))}
                  </div>
                </Card>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 }}>
                  <Card padding="1rem">
                    {selectedUnit ? (
                      <UnitDetails unit={selectedUnit} />
                    ) : (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                        Select a unit in the 3D view or the list to see its dimensions.
                      </p>
                    )}
                  </Card>

                  <Card padding="1rem" style={{ maxHeight: '340px', overflowY: 'auto' }}>
                    <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                      Units ({scene.units.length})
                    </h3>
                    <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {scene.units.map((unit) => {
                        const active = unit.id === selectedUnitId;
                        return (
                          <li key={unit.id}>
                            <button
                              type="button"
                              onClick={() => setSelectedUnitId(unit.id)}
                              aria-pressed={active}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                width: '100%',
                                textAlign: 'left',
                                padding: '0.4rem 0.5rem',
                                borderRadius: '6px',
                                border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                                background: active ? 'var(--surface-hover)' : 'transparent',
                                color: 'var(--foreground)',
                                fontSize: '0.8125rem',
                                cursor: 'pointer',
                              }}
                            >
                              <span
                                aria-hidden="true"
                                style={{
                                  width: '10px',
                                  height: '10px',
                                  borderRadius: '2px',
                                  background: floorColor(scene.floors.findIndex((f) => f.id === unit.floor.id)),
                                }}
                              />
                              {unit.unitIdentifier}
                              <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: '0.75rem' }}>
                                {unit.floor.levelName || unit.floor.floorNumber}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </Card>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </PageContainer>
  );
}
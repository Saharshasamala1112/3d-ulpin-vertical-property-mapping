import { useEffect, useState } from 'react';
import { Card } from '../ui/Card';
import { Select, type SelectOption } from '../ui/Select';
import { toApiError } from '../../lib/api-error';
import { hierarchyService, type HierarchyOption } from '../../services/hierarchy-service';
import type { ValidationScope, ValidationTarget } from '../../types/topology';

interface ValidationTargetPickerProps {
  scope: ValidationScope;
  target: ValidationTarget;
  onScopeChange: (scope: ValidationScope) => void;
  onTargetChange: (target: ValidationTarget) => void;
}

function toOptions(list: HierarchyOption[]): SelectOption[] {
  return list.map((item) => ({ value: item.id, label: item.label }));
}

const scopeButtonStyle = (active: boolean): React.CSSProperties => ({
  padding: '0.375rem 0.75rem',
  fontSize: '0.8125rem',
  fontWeight: 500,
  borderRadius: '6px',
  border: '1px solid var(--border)',
  background: active ? 'var(--primary)' : 'var(--surface-muted)',
  color: active ? 'var(--primary-foreground)' : 'var(--foreground)',
  cursor: 'pointer',
});

export function ValidationTargetPicker({
  scope,
  target,
  onScopeChange,
  onTargetChange,
}: ValidationTargetPickerProps) {
  const [parcels, setParcels] = useState<HierarchyOption[]>([]);
  const [buildings, setBuildings] = useState<HierarchyOption[]>([]);
  const [floors, setFloors] = useState<HierarchyOption[]>([]);
  const [units, setUnits] = useState<HierarchyOption[]>([]);
  const [parcelId, setParcelId] = useState('');
  const [floorId, setFloorId] = useState('');
  const [loadingParcels, setLoadingParcels] = useState(true);
  const [loadingBuildings, setLoadingBuildings] = useState(false);
  const [loadingFloors, setLoadingFloors] = useState(false);
  const [loadingUnits, setLoadingUnits] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    hierarchyService
      .listParcels()
      .then((list) => {
        if (!cancelled) setParcels(list);
      })
      .catch((raw) => {
        if (!cancelled) setError(toApiError(raw).message);
      })
      .finally(() => {
        if (!cancelled) setLoadingParcels(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!parcelId) {
      setBuildings([]);
      return;
    }
    let cancelled = false;
    setLoadingBuildings(true);
    setError(null);
    hierarchyService
      .listBuildings(parcelId)
      .then((list) => {
        if (!cancelled) setBuildings(list);
      })
      .catch((raw) => {
        if (!cancelled) setError(toApiError(raw).message);
      })
      .finally(() => {
        if (!cancelled) setLoadingBuildings(false);
      });
    return () => {
      cancelled = true;
    };
  }, [parcelId]);

  useEffect(() => {
    if (scope !== 'unit' || !target.buildingId) {
      setFloors([]);
      return;
    }
    let cancelled = false;
    setLoadingFloors(true);
    setError(null);
    hierarchyService
      .listFloors(target.buildingId)
      .then((list) => {
        if (!cancelled) setFloors(list);
      })
      .catch((raw) => {
        if (!cancelled) setError(toApiError(raw).message);
      })
      .finally(() => {
        if (!cancelled) setLoadingFloors(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, target.buildingId]);

  useEffect(() => {
    if (scope !== 'unit' || !floorId) {
      setUnits([]);
      return;
    }
    let cancelled = false;
    setLoadingUnits(true);
    setError(null);
    hierarchyService
      .listUnits(floorId)
      .then((list) => {
        if (!cancelled) setUnits(list);
      })
      .catch((raw) => {
        if (!cancelled) setError(toApiError(raw).message);
      })
      .finally(() => {
        if (!cancelled) setLoadingUnits(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, floorId]);

  useEffect(() => {
    setFloorId('');
    setUnits([]);
  }, [scope]);

  const handleParcelChange = (value: string) => {
    setParcelId(value);
    setBuildings([]);
    setFloorId('');
    setUnits([]);
    onTargetChange({});
  };

  const handleBuildingChange = (value: string) => {
    setFloorId('');
    setUnits([]);
    onTargetChange(value ? { buildingId: value } : {});
  };

  const handleFloorChange = (value: string) => {
    setFloorId(value);
    setUnits([]);
    onTargetChange({ buildingId: target.buildingId });
  };

  const handleUnitChange = (value: string) => {
    onTargetChange({
      buildingId: target.buildingId,
      unitId: value || undefined,
    });
  };

  const selectedBuilding = target.buildingId ?? '';

  return (
    <Card padding="1.25rem">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            aria-pressed={scope === 'building'}
            onClick={() => onScopeChange('building')}
            style={scopeButtonStyle(scope === 'building')}
          >
            Whole building
          </button>
          <button
            type="button"
            aria-pressed={scope === 'unit'}
            onClick={() => onScopeChange('unit')}
            style={scopeButtonStyle(scope === 'unit')}
          >
            Single unit
          </button>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '0.75rem',
          }}
        >
          <Select
            label="Parcel"
            placeholder="Select a parcel"
            value={parcelId}
            options={toOptions(parcels)}
            loading={loadingParcels}
            onChange={(event) => handleParcelChange(event.target.value)}
          />
          <Select
            label="Building"
            placeholder="Select a building"
            value={selectedBuilding}
            options={toOptions(buildings)}
            loading={loadingBuildings}
            disabled={!parcelId}
            onChange={(event) => handleBuildingChange(event.target.value)}
          />
          {scope === 'unit' && (
            <>
              <Select
                label="Floor"
                placeholder="Select a floor"
                value={floorId}
                options={toOptions(floors)}
                loading={loadingFloors}
                disabled={!selectedBuilding}
                onChange={(event) => handleFloorChange(event.target.value)}
              />
              <Select
                label="Unit"
                placeholder="Select a unit"
                value={target.unitId ?? ''}
                options={toOptions(units)}
                loading={loadingUnits}
                disabled={!floorId}
                onChange={(event) => handleUnitChange(event.target.value)}
              />
            </>
          )}
        </div>

        {error && (
          <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{error}</span>
        )}
      </div>
    </Card>
  );
}

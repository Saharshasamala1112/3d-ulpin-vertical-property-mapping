import { useEffect, useState } from 'react';
import { Dialog } from '../../../components/ui/Dialog';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { Alert } from '../../../components/ui/Alert';
import { GeoJsonField } from '../shared/GeoJsonField';
import { stringifyGeoJson } from '../shared/geojson';
import { toApiError, type ApiError } from '../../../services/api-error';
import { createBuilding, updateBuilding } from './building-service';
import {
  buildBuildingUpdate,
  emptyBuildingForm,
  validateBuildingForm,
  type BuildingFormValues,
} from './building-validation';
import {
  BUILDING_CONSTRUCTION_STATUSES,
  BUILDING_TYPES,
  type Building,
  type BuildingCreatePayload,
  type BuildingFieldErrors,
} from './building-types';

interface BuildingFormDialogProps {
  open: boolean;
  /** `null` means create mode. */
  building: Building | null;
  /** Required to create: buildings are always created under a parcel. */
  parcelId: string | null;
  onClose: () => void;
  onSaved: (building: Building, mode: 'create' | 'update') => void;
}

function toFormValues(building: Building | null): BuildingFormValues {
  if (!building) return emptyBuildingForm;
  return {
    building_identifier: building.building_identifier,
    name: building.name ?? '',
    building_type: building.building_type,
    construction_status: building.construction_status,
    footprintText: stringifyGeoJson(building.footprint_geometry),
  };
}

function toOriginalPayload(building: Building): BuildingCreatePayload {
  return {
    building_identifier: building.building_identifier,
    name: building.name,
    building_type: building.building_type,
    construction_status: building.construction_status,
    footprint_geometry: building.footprint_geometry,
  };
}

export function BuildingFormDialog({
  open,
  building,
  parcelId,
  onClose,
  onSaved,
}: BuildingFormDialogProps) {
  const isEdit = building !== null;
  const [values, setValues] = useState<BuildingFormValues>(() => toFormValues(building));
  const [errors, setErrors] = useState<BuildingFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setValues(toFormValues(building));
    setErrors({});
    setFormError(null);
    setBusy(false);
  }, [open, building]);

  const setField = <K extends keyof BuildingFormValues>(key: K, value: BuildingFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  };

  const persist = async (run: () => Promise<Building>, mode: 'create' | 'update') => {
    setBusy(true);
    try {
      const saved = await run();
      onSaved(saved, mode);
      onClose();
    } catch (failure) {
      const error: ApiError = toApiError(failure);
      setErrors(error.fieldErrors as BuildingFieldErrors);
      setFormError(
        error.formError ??
          (error.isValidationError
            ? 'The server rejected some fields. Review the highlighted fields.'
            : error.displayMessage)
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);

    if (isEdit && building) {
      const validated = buildBuildingUpdate(toOriginalPayload(building), values);
      if (!validated.ok) {
        setErrors(validated.errors);
        return;
      }
      await persist(() => updateBuilding(building.id, validated.update), 'update');
      return;
    }

    if (!parcelId) {
      setFormError('A parcel must be selected before creating a building.');
      return;
    }

    const validated = validateBuildingForm(values);
    if (!validated.ok) {
      setErrors(validated.errors);
      return;
    }
    await persist(() => createBuilding(parcelId, validated.create), 'create');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit ${building?.building_identifier}` : 'New building'}
      maxWidth="560px"
    >
      <form onSubmit={handleSubmit} noValidate>
        {formError && (
          <div style={{ marginBottom: '1rem' }}>
            <Alert variant="error" title={isEdit ? 'Could not save building' : 'Could not create building'}>
              {formError}
            </Alert>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
          <Input
            label="Building identifier"
            value={values.building_identifier}
            disabled={busy}
            error={errors.building_identifier}
            onChange={(event) => setField('building_identifier', event.target.value)}
          />
          <Input
            label="Name"
            value={values.name}
            disabled={busy}
            error={errors.name}
            onChange={(event) => setField('name', event.target.value)}
          />
          <Select
            label="Building type"
            value={values.building_type}
            disabled={busy}
            error={errors.building_type}
            options={[...BUILDING_TYPES]}
            onChange={(event) => setField('building_type', event.target.value)}
          />
          <Select
            label="Construction status"
            value={values.construction_status}
            disabled={busy}
            error={errors.construction_status}
            options={[...BUILDING_CONSTRUCTION_STATUSES]}
            onChange={(event) => setField('construction_status', event.target.value)}
          />
        </div>

        <div style={{ marginTop: '0.875rem' }}>
          <GeoJsonField
            label="Footprint geometry"
            value={values.footprintText}
            disabled={busy}
            error={errors.footprintText}
            onChange={(value) => setField('footprintText', value)}
          />
        </div>

        <div
          style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}
        >
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {isEdit ? 'Save changes' : 'Create building'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export default BuildingFormDialog;

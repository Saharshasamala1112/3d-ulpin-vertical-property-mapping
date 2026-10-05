import { useEffect, useState } from 'react';
import { Dialog } from '../../../components/ui/Dialog';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { Alert } from '../../../components/ui/Alert';
import { toApiError, type ApiError } from '../../../services/api-error';
import { createFloor, updateFloor } from './floor-service';
import {
  buildFloorUpdate,
  emptyFloorForm,
  validateFloorForm,
  type FloorFormValues,
} from './floor-validation';
import {
  FLOOR_TYPES,
  type Floor,
  type FloorCreatePayload,
  type FloorFieldErrors,
} from './floor-types';

interface FloorFormDialogProps {
  open: boolean;
  /** `null` means create mode. */
  floor: Floor | null;
  /** Required to create: floors are always created under a building. */
  buildingId: string | null;
  onClose: () => void;
  onSaved: (floor: Floor, mode: 'create' | 'update') => void;
}

function toFormValues(floor: Floor | null): FloorFormValues {
  if (!floor) return emptyFloorForm;
  return {
    floor_number: String(floor.floor_number),
    level_name: floor.level_name ?? '',
    floor_type: floor.floor_type,
    elevation_min: String(floor.elevation_min),
    elevation_max: String(floor.elevation_max),
  };
}

function toOriginalPayload(floor: Floor): FloorCreatePayload {
  return {
    floor_number: floor.floor_number,
    level_name: floor.level_name,
    floor_type: floor.floor_type,
    elevation_min: floor.elevation_min,
    elevation_max: floor.elevation_max,
  };
}

export function FloorFormDialog({ open, floor, buildingId, onClose, onSaved }: FloorFormDialogProps) {
  const isEdit = floor !== null;
  const [values, setValues] = useState<FloorFormValues>(() => toFormValues(floor));
  const [errors, setErrors] = useState<FloorFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setValues(toFormValues(floor));
    setErrors({});
    setFormError(null);
    setBusy(false);
  }, [open, floor]);

  const setField = <K extends keyof FloorFormValues>(key: K, value: FloorFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  };

  const persist = async (run: () => Promise<Floor>, mode: 'create' | 'update') => {
    setBusy(true);
    try {
      const saved = await run();
      onSaved(saved, mode);
      onClose();
    } catch (failure) {
      const error: ApiError = toApiError(failure);
      setErrors(error.fieldErrors as FloorFieldErrors);
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

    if (isEdit && floor) {
      const validated = buildFloorUpdate(toOriginalPayload(floor), values);
      if (!validated.ok) {
        setErrors(validated.errors);
        return;
      }
      await persist(() => updateFloor(floor.id, validated.update), 'update');
      return;
    }

    if (!buildingId) {
      setFormError('A building must be selected before creating a floor.');
      return;
    }

    const validated = validateFloorForm(values);
    if (!validated.ok) {
      setErrors(validated.errors);
      return;
    }
    await persist(() => createFloor(buildingId, validated.create), 'create');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit floor ${floor?.floor_number}` : 'New floor'}
      maxWidth="520px"
    >
      <form onSubmit={handleSubmit} noValidate>
        {formError && (
          <div style={{ marginBottom: '1rem' }}>
            <Alert variant="error" title={isEdit ? 'Could not save floor' : 'Could not create floor'}>
              {formError}
            </Alert>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
          <Input
            label="Floor number"
            inputMode="numeric"
            value={values.floor_number}
            disabled={busy}
            error={errors.floor_number}
            onChange={(event) => setField('floor_number', event.target.value)}
          />
          <Input
            label="Level name"
            value={values.level_name}
            disabled={busy}
            error={errors.level_name}
            onChange={(event) => setField('level_name', event.target.value)}
          />
          <Select
            label="Floor type"
            value={values.floor_type}
            disabled={busy}
            error={errors.floor_type}
            options={[...FLOOR_TYPES]}
            onChange={(event) => setField('floor_type', event.target.value)}
          />
          <div />
          <Input
            label="Minimum elevation (m)"
            inputMode="decimal"
            value={values.elevation_min}
            disabled={busy}
            error={errors.elevation_min}
            onChange={(event) => setField('elevation_min', event.target.value)}
          />
          <Input
            label="Maximum elevation (m)"
            inputMode="decimal"
            value={values.elevation_max}
            disabled={busy}
            error={errors.elevation_max}
            onChange={(event) => setField('elevation_max', event.target.value)}
          />
        </div>

        <p style={{ fontSize: '0.75rem', color: 'var(--muted)', margin: '0.75rem 0 0' }}>
          The API does not check that the minimum elevation is below the maximum, so both values are
          saved exactly as entered.
        </p>

        <div
          style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}
        >
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {isEdit ? 'Save changes' : 'Create floor'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export default FloorFormDialog;

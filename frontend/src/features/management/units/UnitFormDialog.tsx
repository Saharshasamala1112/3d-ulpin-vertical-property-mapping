import { useEffect, useState } from 'react';
import { Dialog } from '../../../components/ui/Dialog';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { Alert } from '../../../components/ui/Alert';
import { BoundingBoxFields } from '../shared/BoundingBoxFields';
import { toApiError, type ApiError } from '../../../services/api-error';
import { createUnit, updateUnit } from './unit-service';
import {
  BBOX_RULE_DESCRIPTION,
  buildUnitUpdate,
  UNIT_STATUSES,
  UNIT_TYPES,
  validateUnitForm,
  type FieldErrors,
  type UnitFormValues,
} from './unit-validation';
import type { Unit, UnitCreatePayload } from './unit-types';

interface UnitFormDialogProps {
  open: boolean;
  /** `null` means create mode. */
  unit: Unit | null;
  /** Required to create: units are always created under a floor. */
  floorId: string | null;
  onClose: () => void;
  onSaved: (unit: Unit, mode: 'create' | 'update') => void;
}

const emptyBbox = {
  x_min: '',
  x_max: '',
  y_min: '',
  y_max: '',
  z_min: '',
  z_max: '',
};

function toFormValues(unit: Unit | null): UnitFormValues {
  if (!unit) {
    return {
      unit_identifier: '',
      unit_type: 'residential',
      area_sqm: '',
      status: 'planned',
      vdc_code: '',
      bbox: emptyBbox,
    };
  }
  return {
    unit_identifier: unit.unit_identifier,
    unit_type: unit.unit_type,
    area_sqm: String(unit.area_sqm),
    status: unit.status,
    vdc_code: unit.vdc_code ?? '',
    bbox: {
      x_min: String(unit.x_min),
      x_max: String(unit.x_max),
      y_min: String(unit.y_min),
      y_max: String(unit.y_max),
      z_min: String(unit.z_min),
      z_max: String(unit.z_max),
    },
  };
}

function toOriginalPayload(unit: Unit): UnitCreatePayload {
  return {
    unit_identifier: unit.unit_identifier,
    unit_type: unit.unit_type,
    area_sqm: unit.area_sqm,
    x_min: unit.x_min,
    x_max: unit.x_max,
    y_min: unit.y_min,
    y_max: unit.y_max,
    z_min: unit.z_min,
    z_max: unit.z_max,
    status: unit.status,
    vdc_code: unit.vdc_code,
  };
}

export function UnitFormDialog({ open, unit, floorId, onClose, onSaved }: UnitFormDialogProps) {
  const isEdit = unit !== null;
  const [values, setValues] = useState<UnitFormValues>(() => toFormValues(unit));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setValues(toFormValues(unit));
    setErrors({});
    setFormError(null);
    setBusy(false);
  }, [open, unit]);

  const setField = <K extends keyof UnitFormValues>(key: K, value: UnitFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  };

  const persist = async (run: () => Promise<Unit>, mode: 'create' | 'update') => {
    setBusy(true);
    try {
      const saved = await run();
      onSaved(saved, mode);
      onClose();
    } catch (failure) {
      const error: ApiError = toApiError(failure);
      setErrors(error.fieldErrors as FieldErrors);
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

    if (isEdit && unit) {
      const validated = buildUnitUpdate(toOriginalPayload(unit), values);
      if (!validated.ok) {
        setErrors(validated.errors);
        return;
      }
      await persist(() => updateUnit(unit.id, validated.update), 'update');
      return;
    }

    if (!floorId) {
      setFormError('A floor must be selected before creating a unit.');
      return;
    }

    const validated = validateUnitForm(values);
    if (!validated.ok) {
      setErrors(validated.errors);
      return;
    }
    await persist(() => createUnit(floorId, validated.payload), 'create');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit ${unit?.unit_identifier}` : 'New unit'}
      maxWidth="600px"
    >
      <form onSubmit={handleSubmit} noValidate>
        {formError && (
          <div style={{ marginBottom: '1rem' }}>
            <Alert variant="error" title={isEdit ? 'Could not save unit' : 'Could not create unit'}>
              {formError}
            </Alert>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
          <Input
            label="Unit identifier"
            value={values.unit_identifier}
            disabled={busy}
            error={errors.unit_identifier}
            onChange={(event) => setField('unit_identifier', event.target.value)}
          />
          <Select
            label="Unit type"
            value={values.unit_type}
            disabled={busy}
            error={errors.unit_type}
            options={[...UNIT_TYPES]}
            onChange={(event) => setField('unit_type', event.target.value)}
          />
          <Input
            label="Area (sqm)"
            inputMode="decimal"
            value={values.area_sqm}
            disabled={busy}
            error={errors.area_sqm}
            onChange={(event) => setField('area_sqm', event.target.value)}
          />
          <Select
            label="Status"
            value={values.status}
            disabled={busy}
            error={errors.status}
            options={[...UNIT_STATUSES]}
            onChange={(event) => setField('status', event.target.value)}
          />
          <Input
            label="VDC code"
            value={values.vdc_code}
            disabled={busy}
            error={errors.vdc_code}
            onChange={(event) => setField('vdc_code', event.target.value)}
          />
        </div>

        <div style={{ marginTop: '1rem' }}>
          <BoundingBoxFields
            values={values.bbox}
            errors={errors}
            disabled={busy}
            onChange={(bbox) => setValues((current) => ({ ...current, bbox }))}
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--muted)', margin: '0.5rem 0 0' }}>
            {BBOX_RULE_DESCRIPTION} The current API only rejects min &gt; max, so this form is
            stricter than the server.
          </p>
        </div>

        <div
          style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}
        >
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {isEdit ? 'Save changes' : 'Create unit'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export default UnitFormDialog;

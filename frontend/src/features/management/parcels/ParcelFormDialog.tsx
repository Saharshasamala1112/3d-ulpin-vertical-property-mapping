import { useEffect, useState } from 'react';
import { Dialog } from '../../../components/ui/Dialog';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { Alert } from '../../../components/ui/Alert';
import { Textarea } from '../../../components/ui/Textarea';
import { GeoJsonField } from '../shared/GeoJsonField';
import { stringifyGeoJson } from '../shared/geojson';
import { toApiError, type ApiError } from '../../../services/api-error';
import { createParcel, updateParcel } from './parcel-service';
import {
  buildParcelUpdate,
  emptyParcelForm,
  validateParcelForm,
  type ParcelFormValues,
} from './parcel-validation';
import {
  PARCEL_STATUSES,
  type GeoJSONFeature,
  type ParcelCreatePayload,
  type ParcelFieldErrors,
} from './parcel-types';

interface ParcelFormDialogProps {
  open: boolean;
  /** `null` means create mode. */
  parcel: GeoJSONFeature | null;
  onClose: () => void;
  /** Called after a successful create/update, with the saved feature. */
  onSaved: (parcel: GeoJSONFeature, mode: 'create' | 'update') => void;
}

function toFormValues(parcel: GeoJSONFeature | null): ParcelFormValues {
  if (!parcel) return emptyParcelForm;
  return {
    parcel_identifier: parcel.properties.parcel_identifier,
    ulpin: parcel.properties.ulpin,
    area_sqm: String(parcel.properties.area_sqm),
    status: parcel.properties.status,
    geometryText: stringifyGeoJson(parcel.geometry),
    metadataText:
      parcel.properties.metadata && Object.keys(parcel.properties.metadata).length > 0
        ? stringifyGeoJson(parcel.properties.metadata)
        : '',
  };
}

/** Extract the comparable original values for the partial-update diff. */
function toOriginalPayload(parcel: GeoJSONFeature): ParcelCreatePayload {
  return {
    parcel_identifier: parcel.properties.parcel_identifier,
    ulpin: parcel.properties.ulpin,
    geometry: parcel.geometry as unknown as Record<string, unknown>,
    area_sqm: parcel.properties.area_sqm,
    status: parcel.properties.status,
    metadata: parcel.properties.metadata,
  };
}

export function ParcelFormDialog({ open, parcel, onClose, onSaved }: ParcelFormDialogProps) {
  const isEdit = parcel !== null;
  const [values, setValues] = useState<ParcelFormValues>(() => toFormValues(parcel));
  const [errors, setErrors] = useState<ParcelFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Re-seed the form whenever the dialog opens for a different parcel.
  useEffect(() => {
    if (!open) return;
    setValues(toFormValues(parcel));
    setErrors({});
    setFormError(null);
    setBusy(false);
  }, [open, parcel]);

  const setField = <K extends keyof ParcelFormValues>(key: K, value: ParcelFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    // Clear the stale message as soon as the user edits the field.
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  };

  const persist = async (run: () => Promise<GeoJSONFeature>, mode: 'create' | 'update') => {
    setBusy(true);
    try {
      const saved = await run();
      onSaved(saved, mode);
      onClose();
    } catch (failure) {
      const error: ApiError = toApiError(failure);
      // Server 422s are mapped back onto the controls they refer to. The API
      // reports the payload key (`geometry`) while the form control is named
      // `geometryText`, so translate it rather than dropping the message.
      const fieldErrors = error.fieldErrors as ParcelFieldErrors;
      setErrors({
        ...fieldErrors,
        geometryText: fieldErrors.geometryText ?? fieldErrors.geometry,
      });
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

    if (isEdit && parcel) {
      const validated = buildParcelUpdate(toOriginalPayload(parcel), values);
      if (!validated.ok) {
        setErrors(validated.errors);
        return;
      }
      await persist(() => updateParcel(parcel.id, validated.update), 'update');
      return;
    }

    const validated = validateParcelForm(values);
    if (!validated.ok) {
      setErrors(validated.errors);
      return;
    }
    await persist(() => createParcel(validated.create), 'create');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit ${parcel?.properties.parcel_identifier}` : 'New parcel'}
      maxWidth="640px"
    >
      <form onSubmit={handleSubmit} noValidate>
        {formError && (
          <div style={{ marginBottom: '1rem' }}>
            <Alert variant="error" title={isEdit ? 'Could not save parcel' : 'Could not create parcel'}>
              {formError}
            </Alert>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
          <Input
            label="Parcel identifier"
            value={values.parcel_identifier}
            disabled={busy}
            error={errors.parcel_identifier}
            onChange={(event) => setField('parcel_identifier', event.target.value)}
          />
          <Input
            label="ULPIN"
            value={values.ulpin}
            disabled={busy}
            error={errors.ulpin}
            onChange={(event) => setField('ulpin', event.target.value)}
          />
          <Input
            label="Area (sqm)"
            type="number"
            step="any"
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
            options={[...PARCEL_STATUSES]}
            onChange={(event) => setField('status', event.target.value)}
          />
        </div>

        <div style={{ marginTop: '0.875rem' }}>
          <GeoJsonField
            label="Geometry"
            required
            showTemplate
            value={values.geometryText}
            disabled={busy}
            error={errors.geometryText}
            onChange={(value) => setField('geometryText', value)}
          />
        </div>

        <div style={{ marginTop: '0.875rem' }}>
          <Textarea
            label="Metadata (optional)"
            value={values.metadataText}
            disabled={busy}
            error={errors.metadataText}
            onChange={(event) => setField('metadataText', event.target.value)}
            rows={5}
            spellCheck={false}
            placeholder={'{\n  "survey_ref": "SV-2024-11"\n}'}
            hint="Free-form JSON object stored on the parcel. Leave blank to send null."
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '0.5rem',
            marginTop: '1.25rem',
          }}
        >
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {isEdit ? 'Save changes' : 'Create parcel'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export default ParcelFormDialog;

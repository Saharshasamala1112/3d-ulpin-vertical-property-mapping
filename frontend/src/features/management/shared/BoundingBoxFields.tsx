import { Input } from '../../../components/ui/Input';
import { BBOX_RULE_DESCRIPTION, type BoundingBoxValues, type FieldErrors } from '../units/unit-validation';

interface BoundingBoxFieldsProps {
  values: BoundingBoxValues;
  errors: FieldErrors;
  onChange: (values: BoundingBoxValues) => void;
  disabled?: boolean;
}

const AXES = [
  { axis: 'x', label: 'X' },
  { axis: 'y', label: 'Y' },
  { axis: 'z', label: 'Z' },
] as const;

/**
 * The six bbox inputs, grouped by axis.
 *
 * Range checking lives entirely in `units/unit-validation.ts` (strict
 * `min < max`); this component only renders the fields and displays whatever
 * errors that module produced, including messages coming from a 422 response.
 */
export function BoundingBoxFields({ values, errors, onChange, disabled = false }: BoundingBoxFieldsProps) {
  return (
    <fieldset
      style={{
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '1rem',
        margin: 0,
      }}
    >
      <legend style={{ fontSize: '0.8125rem', fontWeight: 600, padding: '0 0.375rem' }}>
        Bounding box
      </legend>
      <p style={{ fontSize: '0.75rem', color: 'var(--muted)', margin: '0 0 0.75rem' }}>
        {BBOX_RULE_DESCRIPTION}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {AXES.map(({ axis, label }) => {
          const minKey = `${axis}_min` as keyof BoundingBoxValues;
          const maxKey = `${axis}_max` as keyof BoundingBoxValues;
          return (
            <div key={axis}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '0.75rem',
                }}
              >
                <Input
                  label={`${label} min`}
                  type="number"
                  step="any"
                  value={values[minKey]}
                  disabled={disabled}
                  error={errors[minKey]}
                  onChange={(event) => onChange({ ...values, [minKey]: event.target.value })}
                />
                <Input
                  label={`${label} max`}
                  type="number"
                  step="any"
                  value={values[maxKey]}
                  disabled={disabled}
                  error={errors[maxKey]}
                  onChange={(event) => onChange({ ...values, [maxKey]: event.target.value })}
                />
              </div>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

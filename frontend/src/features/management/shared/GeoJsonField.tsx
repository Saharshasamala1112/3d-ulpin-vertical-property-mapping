import { Textarea } from '../../../components/ui/Textarea';
import { Button } from '../../../components/ui/Button';
import { MULTI_POLYGON_TEMPLATE, stringifyGeoJson } from './geojson';

interface GeoJsonFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Field-level message from client validation or a 422 details entry. */
  error?: string;
  required?: boolean;
  /** Offer a MultiPolygon starter template (parcel geometry). */
  showTemplate?: boolean;
  disabled?: boolean;
  id?: string;
}

/**
 * Textarea-based GeoJSON editor with a "Validate" affordance.
 *
 * Validation is performed by the parent through `onChange` + `parseGeoJsonText`
 * so the same rules are shared with unit tests; this component only renders the
 * control and the optional template helper.
 */
export function GeoJsonField({
  label,
  value,
  onChange,
  error,
  required = false,
  showTemplate = false,
  disabled = false,
  id,
}: GeoJsonFieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
      <Textarea
        id={id}
        label={`${label}${required ? '' : ' (optional)'}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        error={error}
        disabled={disabled}
        rows={8}
        spellCheck={false}
        placeholder={'{\n  "type": "MultiPolygon",\n  "coordinates": []\n}'}
        hint="Paste a GeoJSON geometry object. The API does not deep-validate geometry content, so malformed coordinates are rejected here."
        style={{ minHeight: '9rem' }}
      />
      {showTemplate && (
        <div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onChange(stringifyGeoJson(MULTI_POLYGON_TEMPLATE))}
            disabled={disabled}
          >
            Insert example MultiPolygon
          </Button>
        </div>
      )}
    </div>
  );
}

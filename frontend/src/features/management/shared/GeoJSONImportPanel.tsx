import { useState } from 'react';
import { Alert } from '../../../components/ui/Alert';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { toApiError, type ApiError } from '../../../services/api-error';
import {
  importBuildingsGeoJSON,
  importParcelsGeoJSON,
} from '../parcels/parcel-service';
import type {
  GeoJSONFeatureImportResult,
  GeoJSONImportCollection,
  GeoJSONImportReport,
} from './geojson-import';
import {
  MAX_GEOJSON_IMPORT_BYTES,
  MAX_GEOJSON_IMPORT_FEATURES,
} from './geojson-import';

type ImportKind = 'parcels' | 'buildings';

interface GeoJSONImportPanelProps {
  onImported: () => void;
  onClose: () => void;
}

function isFeatureCollection(value: unknown): value is GeoJSONImportCollection {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    'type' in value &&
    value.type === 'FeatureCollection' &&
    'features' in value &&
    Array.isArray(value.features) &&
    value.features.length > 0 &&
    value.features.length <= MAX_GEOJSON_IMPORT_FEATURES
  );
}

function summaryText(report: GeoJSONImportReport): string {
  return `${report.created} created, ${report.updated} updated, ${report.skipped} unchanged, ${report.failed} failed.`;
}

function FeatureOutcomeTable({ features }: { features: GeoJSONFeatureImportResult[] }) {
  return (
    <div style={{ overflowX: 'auto', marginTop: '0.75rem' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
        <thead>
          <tr>
            <th scope="col" style={cellStyle}>Feature</th>
            <th scope="col" style={cellStyle}>Key</th>
            <th scope="col" style={cellStyle}>Result</th>
            <th scope="col" style={cellStyle}>Details</th>
          </tr>
        </thead>
        <tbody>
          {features.map((feature) => (
            <tr key={feature.index}>
              <td style={cellStyle}>{feature.index}</td>
              <td style={cellStyle}>{feature.key || '—'}</td>
              <td style={cellStyle}>{feature.status}</td>
              <td style={cellStyle}>{feature.reason || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  borderBottom: '1px solid var(--border)',
  padding: '0.5rem',
  textAlign: 'left',
  verticalAlign: 'top',
};

export function GeoJSONImportPanel({ onImported, onClose }: GeoJSONImportPanelProps) {
  const [kind, setKind] = useState<ImportKind>('parcels');
  const [collection, setCollection] = useState<GeoJSONImportCollection | null>(null);
  const [fileName, setFileName] = useState('');
  const [ulpinProperty, setUlpInProperty] = useState('ulpin');
  const [parcelId, setParcelId] = useState('');
  const [report, setReport] = useState<GeoJSONImportReport | null>(null);
  const [error, setError] = useState<ApiError | string | null>(null);
  const [busy, setBusy] = useState(false);

  const chooseFile = async (file: File | undefined) => {
    setCollection(null);
    setFileName('');
    setReport(null);
    setError(null);
    if (!file) return;
    if (file.size > MAX_GEOJSON_IMPORT_BYTES) {
      setError(`Choose a file no larger than ${MAX_GEOJSON_IMPORT_BYTES / (1024 * 1024)} MiB.`);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (!isFeatureCollection(parsed)) {
        setError(`Choose a FeatureCollection containing 1 to ${MAX_GEOJSON_IMPORT_FEATURES} features.`);
        return;
      }
      setCollection(parsed);
      setFileName(file.name);
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : String(failure);
      setError(`Could not read GeoJSON: ${detail}`);
    }
  };

  const runImport = async (dryRun: boolean) => {
    if (!collection) return;
    setBusy(true);
    setError(null);
    try {
      const result =
        kind === 'parcels'
          ? await importParcelsGeoJSON(collection, {
              dryRun,
              ulpinProperty: ulpinProperty.trim() || 'ulpin',
            })
          : await importBuildingsGeoJSON(collection, { dryRun, parcelId });
      setReport(result);
      if (!dryRun) onImported();
    } catch (failure) {
      setError(toApiError(failure));
    } finally {
      setBusy(false);
    }
  };

  const updateSetting = (update: () => void) => {
    update();
    setReport(null);
    setError(null);
  };

  const canCommit = report !== null && report.dry_run && report.features.some(
    (feature) => feature.status !== 'failed'
  );

  return (
    <section
      aria-labelledby="geojson-import-title"
      style={{
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '1rem',
        marginBottom: '1rem',
        background: 'var(--surface)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <h2 id="geojson-import-title" style={{ margin: '0 0 0.25rem', fontSize: '1rem' }}>
            Import GeoJSON
          </h2>
          <p style={{ margin: 0, color: 'var(--muted)', fontSize: '0.8125rem' }}>
            Preview validates every feature without writing. Confirm the preview to import valid
            features; individual errors do not stop the rest of the batch.
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose} aria-label="Close GeoJSON import">
          Close
        </Button>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '0.75rem',
          marginTop: '1rem',
          alignItems: 'end',
        }}
      >
        <Select
          label="Data to import"
          value={kind}
          options={[
            { value: 'parcels', label: 'Parcels' },
            { value: 'buildings', label: 'Building footprints' },
          ]}
          onChange={(event) => updateSetting(() => setKind(event.target.value as ImportKind))}
        />
        <Input
          type="file"
          label="GeoJSON file"
          accept=".json,.geojson,application/json,application/geo+json"
          onChange={(event) => void chooseFile(event.target.files?.[0])}
        />
        {kind === 'parcels' ? (
          <Input
            label="ULPIN property"
            value={ulpinProperty}
            onChange={(event) => updateSetting(() => setUlpInProperty(event.target.value))}
            placeholder="ulpin"
          />
        ) : (
          <Input
            label="Default parcel ID (optional)"
            value={parcelId}
            onChange={(event) => updateSetting(() => setParcelId(event.target.value))}
            placeholder="Parcel UUID; can also be set per feature"
          />
        )}
      </div>

      <p style={{ color: 'var(--muted)', fontSize: '0.75rem', margin: '0.5rem 0 0' }}>
        Maximum file size: 10 MiB; maximum features: 500.
        {kind === 'parcels'
          ? ' Required properties: ULPIN, parcel_identifier (or name), and positive area_sqm.'
          : ' Required properties: building_identifier (or name) and parcel_id on the feature or above.'}
      </p>
      {fileName && (
        <p style={{ fontSize: '0.8125rem', margin: '0.5rem 0 0' }}>Selected: {fileName}</p>
      )}

      {error && (
        <div style={{ marginTop: '0.75rem' }}>
          <Alert variant="error" title="GeoJSON import failed">
            {typeof error === 'string' ? error : error.displayMessage}
          </Alert>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
        <Button type="button" onClick={() => void runImport(true)} disabled={!collection} loading={busy}>
          Preview import
        </Button>
        {canCommit && (
          <Button type="button" variant="secondary" onClick={() => void runImport(false)} loading={busy}>
            Confirm and import valid features
          </Button>
        )}
      </div>

      {report && (
        <div style={{ marginTop: '1rem' }}>
          <Alert variant={report.failed ? 'warning' : report.dry_run ? 'info' : 'success'}>
            <strong>{report.dry_run ? 'Preview only — no data was written.' : 'Import complete.'}</strong>{' '}
            {summaryText(report)}
          </Alert>
          <FeatureOutcomeTable features={report.features} />
        </div>
      )}
    </section>
  );
}

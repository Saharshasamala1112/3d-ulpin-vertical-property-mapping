export const MAX_GEOJSON_IMPORT_BYTES = 10 * 1024 * 1024;
export const MAX_GEOJSON_IMPORT_FEATURES = 500;

export interface GeoJSONImportCollection {
  type: 'FeatureCollection';
  features: unknown[];
}

export type GeoJSONImportStatus = 'created' | 'updated' | 'skipped' | 'failed';

export interface GeoJSONFeatureImportResult {
  index: number;
  status: GeoJSONImportStatus;
  key: string | null;
  record_id: string | null;
  reason: string | null;
}

export interface GeoJSONImportReport {
  dry_run: boolean;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  features: GeoJSONFeatureImportResult[];
}

// Typed helpers for the ScorePilot HTTP API.

export type ColumnType = 'quantitative' | 'qualitative' | 'datetime' | 'unknown';
export type IdentifierRole = 'none' | 'primary' | 'secondary' | 'class';
export type TransformKind =
  | 'none'
  | 'linear'
  | 'log'
  | 'neglog'
  | 'logit'
  | 'exponential'
  | 'power';
export type ScalingKind = 'none' | 'unit_variance' | 'pareto';

export interface ColumnMeta {
  name: string;
  column_type: ColumnType;
  identifier_role: IdentifierRole;
}

export interface DatasetDetail {
  dataset_id: string;
  name: string;
  source: string;
  sheet: string | null;
  sheets: string[];
  n_rows: number;
  n_columns: number;
  primary_id: string | null;
  columns: ColumnMeta[];
}

export interface GridWindow {
  row_offset: number;
  column_names: string[];
  row_identifiers: (string | null)[];
  cells: (string | null)[][];
}

export interface VariableInspector {
  name: string;
  column_type: ColumnType;
  n: number;
  n_missing: number;
  pct_missing: number;
  n_unique: number;
  mean: number | null;
  std: number | null;
  minimum: number | null;
  maximum: number | null;
  median: number | null;
  q25: number | null;
  q75: number | null;
  skewness: number | null;
  min_max_ratio: number | null;
  suggested_transform: TransformKind;
  histogram_counts: number[];
  histogram_edges: number[];
  sequence: (number | null)[];
}

export interface ColumnQuality {
  name: string;
  n_missing: number;
  pct_missing: number;
  n_invalid: number;
  invalid_rows: number[];
  exceeds_tolerance: boolean;
}

export interface ObservationQuality {
  index: number;
  identifier: string | null;
  n_missing: number;
  pct_missing: number;
}

export interface DuplicateIdentifier {
  value: string;
  rows: number[];
}

export interface QualityReport {
  n_rows: number;
  n_columns: number;
  n_missing_cells: number;
  pct_missing: number;
  primary_id_unique: boolean;
  duplicate_primary_ids: DuplicateIdentifier[];
  columns: ColumnQuality[];
  observations_exceeding: ObservationQuality[];
}

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
    } catch {
      // no JSON body
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return (await response.json()) as T;
}

export async function uploadDataset(file: File, sheet?: string): Promise<DatasetDetail> {
  const form = new FormData();
  form.append('file', file);
  const query = sheet ? `?sheet=${encodeURIComponent(sheet)}` : '';
  return asJson(await fetch(`/api/datasets${query}`, { method: 'POST', body: form }));
}

export async function listDatasets(): Promise<DatasetDetail[]> {
  return asJson(await fetch('/api/datasets'));
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  return asJson(await fetch(`/api/datasets/${id}`));
}

export interface SampleInfo {
  name: string;
  title: string;
  description: string;
  source_url: string;
}

export async function listSamples(): Promise<SampleInfo[]> {
  return asJson(await fetch('/api/datasets/samples'));
}

export async function loadSample(name: string): Promise<DatasetDetail> {
  return asJson(await fetch(`/api/datasets/samples/${encodeURIComponent(name)}`, { method: 'POST' }));
}

export async function patchColumn(
  id: string,
  column: string,
  update: { column_type?: ColumnType; identifier_role?: IdentifierRole }
): Promise<DatasetDetail> {
  return asJson(
    await fetch(`/api/datasets/${id}/columns/${encodeURIComponent(column)}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(update)
    })
  );
}

/** Fetch the full grid by paging the windowed endpoint. */
export async function getGridAll(id: string, form: 'raw' | 'scaled' = 'raw'): Promise<GridWindow> {
  const pageSize = 1000;
  let offset = 0;
  const cells: (string | null)[][] = [];
  const rowIds: (string | null)[] = [];
  let columnNames: string[] = [];
  for (;;) {
    const window = await asJson<GridWindow>(
      await fetch(`/api/datasets/${id}/grid?row_offset=${offset}&row_limit=${pageSize}&form=${form}`)
    );
    columnNames = window.column_names;
    cells.push(...window.cells);
    rowIds.push(...window.row_identifiers);
    if (window.cells.length < pageSize) break;
    offset += pageSize;
  }
  return { row_offset: 0, column_names: columnNames, row_identifiers: rowIds, cells };
}

export async function getVariable(
  id: string,
  column: string,
  transform: TransformKind = 'none'
): Promise<VariableInspector> {
  const query = transform === 'none' ? '' : `?transform=${transform}`;
  return asJson(
    await fetch(`/api/datasets/${id}/variables/${encodeURIComponent(column)}${query}`)
  );
}

export async function getQuality(id: string): Promise<QualityReport> {
  return asJson(await fetch(`/api/datasets/${id}/quality`));
}

export interface ScoresPayload {
  component_names: string[];
  observation_names: string[];
  data: number[][];
}

export interface PCAFitResponse {
  model_id: number;
  kind: string;
  n_components: number;
  conf_level: number;
  component_names: string[];
  explained_variance: number[];
  r2_cumulative: number[];
  scores: ScoresPayload;
  hotellings_t2: number[];
  spe: number[];
  t2_limit: number;
  spe_limit: number;
}

export async function fitPca(datasetId: string, nComponents: number): Promise<PCAFitResponse> {
  return asJson(
    await fetch('/api/models/pca', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, n_components: nComponents })
    })
  );
}

// --- Models: Hangar and Logbook ---

export interface ModelSummary {
  id: number;
  kind: string;
  name: string | null;
  n_components: number;
  parent_id: number | null;
  dataset_id: string | null;
  created_at: string;
}

export interface LoadingsPayload {
  component_names: string[];
  variable_names: string[];
  data: number[][];
}

export interface ModelDiagnostics {
  kind: string;
  n_components: number;
  conf_level: number;
  component_names: string[];
  explained_variance: number[];
  r2_per_component: number[];
  r2_cumulative: number[];
  scores: ScoresPayload;
  x_loadings: LoadingsPayload;
  y_loadings: LoadingsPayload | null;
  hotellings_t2: number[];
  spe: number[];
  t2_limit: number;
  spe_limit: number;
  ellipse_x: number[];
  ellipse_y: number[];
  vip: Record<string, number>;
}

export interface ModelDetail {
  summary: ModelSummary;
  preprocessing: Record<string, unknown>;
  excluded_samples: number[];
  lineage: ModelSummary[];
  diagnostics: ModelDiagnostics | null;
}

export interface FitModelRequest {
  dataset_id: string;
  kind: 'PCA' | 'PLS';
  n_components: number;
  name?: string | null;
  parent_id?: number | null;
  spec?: Record<string, unknown>;
}

export async function fitModel(request: FitModelRequest): Promise<ModelDetail> {
  return asJson(
    await fetch('/api/models', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(request)
    })
  );
}

export async function listModels(): Promise<ModelSummary[]> {
  return asJson(await fetch('/api/models'));
}

export async function getModel(id: number): Promise<ModelDetail> {
  return asJson(await fetch(`/api/models/${id}`));
}

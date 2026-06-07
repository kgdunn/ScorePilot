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
  /** Primary-identifier value per row, aligned with `sequence` (issue #59). */
  identifiers?: (string | null)[];
  /** Whether the primary identifier is genuinely sequential (synthetic Row or a
   * monotonic run order); when false, plots label points by the identifier. */
  is_sequential?: boolean;
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

/** Import a dataset from a CSV/Excel file at a public URL (max 5 MB). */
export async function openDatasetFromUrl(url: string): Promise<DatasetDetail> {
  return asJson(
    await fetch('/api/datasets/from-url', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url })
    })
  );
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
export async function getGridAll(
  id: string,
  form: 'raw' | 'scaled' = 'raw',
  transforms?: Record<string, { kind: TransformKind; c1: number; c2: number }>
): Promise<GridWindow> {
  const pageSize = 1000;
  let offset = 0;
  const cells: (string | null)[][] = [];
  const rowIds: (string | null)[] = [];
  let columnNames: string[] = [];
  // Transforms only affect the scaled view; skip the param otherwise.
  const transformParam =
    form === 'scaled' && transforms && Object.keys(transforms).length
      ? `&transforms=${encodeURIComponent(JSON.stringify(transforms))}`
      : '';
  for (;;) {
    const window = await asJson<GridWindow>(
      await fetch(
        `/api/datasets/${id}/grid?row_offset=${offset}&row_limit=${pageSize}&form=${form}${transformParam}`
      )
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
  transform: TransformKind = 'none',
  form: 'raw' | 'scaled' = 'raw',
  excludedRows: number[] = []
): Promise<VariableInspector> {
  const params = new URLSearchParams();
  if (transform !== 'none') params.set('transform', transform);
  if (form !== 'raw') params.set('form', form);
  for (const r of excludedRows) params.append('excluded_rows', String(r));
  const query = params.toString() ? `?${params}` : '';
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
  /** Choose the component count by cross-validation instead of n_components. */
  auto_components?: boolean;
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

export async function getModel(id: number, nComponents?: number): Promise<ModelDetail> {
  const q = nComponents ? `?n_components=${nComponents}` : '';
  return asJson(await fetch(`/api/models/${id}${q}`));
}

/** Change a model's component count in place (no new variant) and refit. */
export async function updateModelComponents(id: number, nComponents: number): Promise<ModelDetail> {
  return asJson(
    await fetch(`/api/models/${id}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ n_components: nComponents })
    })
  );
}

export interface Contributions {
  observation: number;
  observation_name: string;
  variable_names: string[];
  t2: number[];
  spe: number[];
}

/** Per-variable contributions of one observation to the model's T2 and SPE. */
export async function getContributions(
  modelId: number,
  observation: number
): Promise<Contributions> {
  return asJson(await fetch(`/api/models/${modelId}/contributions/${observation}`));
}

/** How the recommended component count is chosen. "randomization" is PLS-only. */
export type SelectionRule = '1se' | 'min' | 'q2_increment' | 'randomization';
/** PCA cross-validation scheme. */
export type CvScheme = 'ekf' | 'row_wise';

export interface CrossValidation {
  kind: string;
  /** What R²/Q² describe: "X" for PCA, "Y" for PLS. */
  target: string;
  n_splits: number;
  n_repeats: number;
  /** Rule used to pick `recommended`. */
  selection_rule: SelectionRule;
  /** PCA cross-validation scheme; null for PLS. */
  cv_scheme: CvScheme | null;
  component_numbers: number[];
  r2: number[];
  q2: number[];
  r2_per_component: number[];
  q2_per_component: number[];
  recommended: number;
  /** Whether the PLS recommendation was stable across CV repeats; null otherwise. */
  recommended_is_stable: boolean | null;
}

/** Options controlling how the recommended component count is chosen. */
export interface CrossValidationOptions {
  maxComponents?: number;
  selectionRule?: SelectionRule;
  cvScheme?: CvScheme;
  nRepeats?: number;
  minQ2Increase?: number;
}

/** Per-component calibration R² and cross-validated Q² for a fitted model. */
export async function getCrossValidation(
  modelId: number,
  options: CrossValidationOptions = {}
): Promise<CrossValidation> {
  const params = new URLSearchParams();
  if (options.maxComponents != null) params.set('max_components', String(options.maxComponents));
  if (options.selectionRule) params.set('selection_rule', options.selectionRule);
  if (options.cvScheme) params.set('cv_scheme', options.cvScheme);
  if (options.nRepeats != null) params.set('n_repeats', String(options.nRepeats));
  if (options.minQ2Increase != null) params.set('min_q2_increase', String(options.minQ2Increase));
  const q = params.toString();
  return asJson(await fetch(`/api/models/${modelId}/cross-validation${q ? `?${q}` : ''}`));
}

export interface VariantRequest {
  /** Primary-identifier values of selected observations. */
  observations?: string[];
  /** Selected variable (column) names. */
  variables?: string[];
  /** Exclude the selection, or keep only the selected observations. */
  mode?: 'exclude' | 'keep';
  name?: string;
}

/** Fork a child model variant from a brushed selection (excludes / keep-only). */
export async function createVariant(
  modelId: number,
  body: VariantRequest
): Promise<ModelDetail> {
  return asJson(
    await fetch(`/api/models/${modelId}/variant`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    })
  );
}

/** The running backend version, shown in the UI so you can confirm the deploy. */
export async function getVersion(): Promise<string> {
  const body = await asJson<{ version: string }>(await fetch('/api/version'));
  return body.version;
}

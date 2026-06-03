// Typed helpers for the ScorePilot HTTP API.

export interface DatasetSummary {
  dataset_id: string;
  n_rows: number;
  n_columns: number;
  columns: string[];
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
  preprocessing: string;
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

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
    } catch {
      // response had no JSON body; keep the status text.
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return (await response.json()) as T;
}

export async function uploadDataset(file: File): Promise<DatasetSummary> {
  const form = new FormData();
  form.append('file', file);
  const response = await fetch('/api/datasets', { method: 'POST', body: form });
  return asJson<DatasetSummary>(response);
}

export async function fitPca(datasetId: string, nComponents: number): Promise<PCAFitResponse> {
  const response = await fetch('/api/models/pca', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, n_components: nComponents })
  });
  return asJson<PCAFitResponse>(response);
}

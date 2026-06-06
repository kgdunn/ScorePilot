<script lang="ts">
  import { fitPca, uploadDataset, type DatasetDetail, type PCAFitResponse } from '$lib/api';
  import { ScatterPlot, type PlotPoint } from '$lib/plots';

  let file = $state<File | null>(null);
  let dataset = $state<DatasetDetail | null>(null);
  let nComponents = $state(2);
  let result = $state<PCAFitResponse | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  function onFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    file = input.files?.[0] ?? null;
    dataset = null;
    result = null;
    error = null;
  }

  async function onUpload() {
    if (!file) return;
    busy = true;
    error = null;
    try {
      dataset = await uploadDataset(file);
      result = null;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function onFit() {
    if (!dataset) return;
    busy = true;
    error = null;
    try {
      result = await fitPca(dataset.dataset_id, nComponents);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  function pct(fit: PCAFitResponse, i: number): number {
    const prev = i === 0 ? 0 : fit.r2_cumulative[i - 1];
    return (fit.r2_cumulative[i] - prev) * 100;
  }

  function scorePoints(fit: PCAFitResponse): PlotPoint[] {
    return fit.scores.data.map((row, i) => ({
      rowId: fit.scores.observation_names[i],
      label: fit.scores.observation_names[i],
      x: row[0],
      y: row[1] ?? 0
    }));
  }
  const xName = $derived(result ? `${result.component_names[0]} (${pct(result, 0).toFixed(1)}%)` : '');
  const yName = $derived(
    result && result.component_names[1] ? `${result.component_names[1]} (${pct(result, 1).toFixed(1)}%)` : 'PC2'
  );
</script>

<main>
  <p class="nav"><a href="/">← Home</a></p>
  <h1>PCA scores playground</h1>
  <p class="hint">A quick fit over all quantitative columns, with default autoscaling.</p>

  <section class="panel">
    <div class="row">
      <input type="file" accept=".csv,.xlsx,.xls" onchange={onFileChange} />
      <button onclick={onUpload} disabled={!file || busy}>Upload</button>
    </div>
    {#if dataset}
      <p class="ok">Loaded {dataset.n_rows} × {dataset.n_columns}.</p>
    {/if}
  </section>

  <section class="panel">
    <div class="row">
      <label>Components <input type="number" min="1" max="20" bind:value={nComponents} /></label>
      <button onclick={onFit} disabled={!dataset || busy}>Fit PCA</button>
    </div>
  </section>

  {#if error}<p class="error">{error}</p>{/if}

  {#if result}
    <section class="panel">
      <h2>Scores</h2>
      <ScatterPlot points={scorePoints(result)} {xName} {yName} height="460px" />
    </section>
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    color: #1c1c1c;
    background: #fafafa;
  }
  main {
    max-width: 52rem;
    margin: 1.5rem auto;
    padding: 0 1.5rem;
  }
  .nav {
    font-size: 0.85rem;
  }
  .panel {
    background: #fff;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
  }
  .row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }
  input[type='number'] {
    width: 4.5rem;
    padding: 0.3rem;
  }
  button {
    padding: 0.4rem 0.9rem;
    border: 1px solid #2b6cb0;
    background: #2b6cb0;
    color: #fff;
    border-radius: 6px;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
  }
  .hint {
    color: #777;
  }
  .ok {
    color: #237a3a;
  }
  .error {
    color: #b3261e;
    font-weight: 600;
  }
</style>

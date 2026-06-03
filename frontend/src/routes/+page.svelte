<script lang="ts">
  import type { ECharts } from 'echarts';
  import { fitPca, uploadDataset, type DatasetSummary, type PCAFitResponse } from '$lib/api';
  import { initChart, scoresScatterOption, type ScorePoint } from '$lib/echarts';

  let file = $state<File | null>(null);
  let dataset = $state<DatasetSummary | null>(null);
  let nComponents = $state(2);
  let result = $state<PCAFitResponse | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  let chartEl = $state<HTMLDivElement | null>(null);
  let chart: ECharts | null = null;

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

  function percentOfTotal(fit: PCAFitResponse, index: number): number {
    const previous = index === 0 ? 0 : fit.r2_cumulative[index - 1];
    return (fit.r2_cumulative[index] - previous) * 100;
  }

  function axisLabel(fit: PCAFitResponse, index: number): string {
    const name = fit.component_names[index] ?? `PC${index + 1}`;
    if (fit.r2_cumulative[index] === undefined) return name;
    return `${name} (${percentOfTotal(fit, index).toFixed(1)}%)`;
  }

  $effect(() => {
    if (!result || !chartEl) return;
    chart ??= initChart(chartEl);
    const fit = result;
    const points: ScorePoint[] = fit.scores.data.map((row, i) => [
      row[0],
      row[1] ?? 0,
      fit.scores.observation_names[i]
    ]);
    chart.setOption(scoresScatterOption(points, axisLabel(fit, 0), axisLabel(fit, 1)), true);
  });

  $effect(() => {
    return () => chart?.dispose();
  });
</script>

<main>
  <h1>ScorePilot</h1>
  <p class="tagline">PCA / PLS model analysis for chemometrics.</p>

  <section class="panel">
    <h2>1. Upload a dataset</h2>
    <p class="hint">CSV with sample identifiers in the first column and numeric variables after.</p>
    <div class="row">
      <input type="file" accept=".csv,text/csv" onchange={onFileChange} />
      <button onclick={onUpload} disabled={!file || busy}>Upload</button>
    </div>
    {#if dataset}
      <p class="ok">
        Loaded <strong>{dataset.n_rows}</strong> samples ×
        <strong>{dataset.n_columns}</strong> variables.
      </p>
    {/if}
  </section>

  <section class="panel">
    <h2>2. Fit PCA</h2>
    <div class="row">
      <label>
        Components
        <input type="number" min="1" max="20" bind:value={nComponents} />
      </label>
      <button onclick={onFit} disabled={!dataset || busy}>Fit PCA</button>
    </div>
  </section>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if result}
    <section class="panel">
      <h2>Scores</h2>
      <p class="hint">
        Model #{result.model_id} · {result.n_components} components · cumulative
        R²X = {(result.r2_cumulative[result.r2_cumulative.length - 1] * 100).toFixed(1)}%
      </p>
      <div class="chart" bind:this={chartEl}></div>
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
    margin: 2.5rem auto;
    padding: 0 1.5rem;
  }
  h1 {
    margin-bottom: 0.1rem;
  }
  .tagline {
    margin-top: 0;
    color: #666;
  }
  .panel {
    background: #fff;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
  }
  .panel h2 {
    margin-top: 0;
    font-size: 1.05rem;
  }
  .row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }
  label {
    display: flex;
    gap: 0.4rem;
    align-items: center;
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
    cursor: not-allowed;
  }
  .hint {
    color: #777;
    font-size: 0.9rem;
  }
  .ok {
    color: #237a3a;
  }
  .error {
    color: #b3261e;
    font-weight: 600;
  }
  .chart {
    width: 100%;
    height: 460px;
  }
</style>

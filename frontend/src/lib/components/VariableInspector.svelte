<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { ECharts } from 'echarts';
  import { getVariable, type TransformKind, type VariableInspector } from '$lib/api';
  import { histogramOption, initChart, sequenceOption } from '$lib/echarts';

  interface Props {
    datasetId: string;
    column: string;
    onApplyTransform?: (column: string, transform: TransformKind) => void;
  }
  let { datasetId, column, onApplyTransform }: Props = $props();

  const TRANSFORMS: TransformKind[] = [
    'none',
    'log',
    'neglog',
    'logit',
    'exponential',
    'power',
    'linear'
  ];

  let info = $state<VariableInspector | null>(null);
  let transform = $state<TransformKind>('none');
  let error = $state<string | null>(null);

  let histEl = $state<HTMLDivElement | null>(null);
  let seqEl = $state<HTMLDivElement | null>(null);
  let histChart: ECharts | null = null;
  let seqChart: ECharts | null = null;

  // Reset the preview when the selected column changes.
  $effect(() => {
    if (column) transform = 'none';
  });

  $effect(() => {
    const ds = datasetId;
    const col = column;
    const t = transform;
    void (async () => {
      try {
        info = await getVariable(ds, col, t);
        error = null;
      } catch (e) {
        error = (e as Error).message;
      }
    })();
  });

  $effect(() => {
    if (!info || !histEl || !seqEl) return;
    histChart ??= initChart(histEl);
    seqChart ??= initChart(seqEl);
    if (info.histogram_counts.length) {
      histChart.setOption(histogramOption(info.histogram_counts, info.histogram_edges), true);
    } else {
      histChart.clear();
    }
    seqChart.setOption(sequenceOption(info.sequence), true);
  });

  onDestroy(() => {
    histChart?.dispose();
    seqChart?.dispose();
  });

  function fmt(value: number | null): string {
    if (value === null) return '—';
    return Number(value).toPrecision(4);
  }
</script>

<div class="inspector">
  <h3>{column}</h3>
  {#if error}<p class="error">{error}</p>{/if}

  {#if info}
    <table class="stats">
      <tbody>
        <tr><th>Type</th><td>{info.column_type}</td><th>N</th><td>{info.n}</td></tr>
        <tr>
          <th>Missing</th><td>{info.n_missing} ({fmt(info.pct_missing)}%)</td>
          <th>Unique</th><td>{info.n_unique}</td>
        </tr>
        <tr><th>Mean</th><td>{fmt(info.mean)}</td><th>Std</th><td>{fmt(info.std)}</td></tr>
        <tr><th>Min</th><td>{fmt(info.minimum)}</td><th>Max</th><td>{fmt(info.maximum)}</td></tr>
        <tr>
          <th>Skewness</th><td>{fmt(info.skewness)}</td>
          <th>Min/Max</th><td>{fmt(info.min_max_ratio)}</td>
        </tr>
      </tbody>
    </table>

    {#if info.column_type === 'quantitative'}
      <div class="transform-row">
        <label>
          Transform
          <select bind:value={transform}>
            {#each TRANSFORMS as t (t)}<option value={t}>{t}</option>{/each}
          </select>
        </label>
        {#if info.suggested_transform !== 'none'}
          <span class="suggest">suggested: <strong>{info.suggested_transform}</strong></span>
        {/if}
        <button onclick={() => onApplyTransform?.(column, transform)} disabled={!onApplyTransform}>
          Apply to spec
        </button>
      </div>

      <h4>Frequency</h4>
      <div class="chart" bind:this={histEl}></div>
      <h4>Sequence</h4>
      <div class="chart" bind:this={seqEl}></div>
    {:else}
      <p class="hint">Distribution and transforms apply to quantitative variables.</p>
    {/if}
  {/if}
</div>

<style>
  .inspector h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }
  .stats {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-bottom: 0.75rem;
  }
  .stats th {
    text-align: left;
    color: #666;
    font-weight: 600;
    padding: 2px 6px;
    width: 22%;
  }
  .stats td {
    padding: 2px 6px;
  }
  .transform-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }
  .suggest {
    color: #777;
    font-size: 0.8rem;
  }
  .chart {
    width: 100%;
    height: 200px;
  }
  h4 {
    margin: 0.5rem 0 0.2rem;
    font-size: 0.85rem;
    color: #444;
  }
  .error {
    color: #b3261e;
  }
  .hint {
    color: #777;
    font-size: 0.85rem;
  }
  button {
    padding: 0.25rem 0.6rem;
    border: 1px solid #2b6cb0;
    background: #2b6cb0;
    color: #fff;
    border-radius: 5px;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
  }
  select {
    padding: 0.2rem;
  }
</style>

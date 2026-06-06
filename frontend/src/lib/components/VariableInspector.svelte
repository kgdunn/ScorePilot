<script lang="ts">
  import { getVariable, type TransformKind, type VariableInspector } from '$lib/api';
  import { Histogram, LinePlot, fmtNum, type LinkGroup } from '$lib/plots';

  interface Props {
    datasetId: string;
    column: string;
    form?: 'raw' | 'scaled';
    appliedTransform?: TransformKind;
    excludedRows?: number[];
    /** Shared brushing context: selected rows are highlighted in the sequence plot. */
    link?: LinkGroup;
    onApplyTransform?: (column: string, transform: TransformKind) => void;
  }
  let {
    datasetId,
    column,
    form = 'raw',
    appliedTransform = 'none',
    excludedRows = [],
    link,
    onApplyTransform
  }: Props = $props();

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

  // Issue #59: label the sequence x-axis by the primary identifier unless the
  // data is genuinely sequential (a synthetic Row column or a monotonic order).
  const seqLabels = $derived(
    info && info.identifiers && !info.is_sequential ? info.identifiers.map((v) => v ?? '') : undefined
  );
  // Selected rows (by identifier) become red-square highlights in the sequence.
  const seqHighlight = $derived.by(() => {
    if (!info?.identifiers || !link) return [];
    const out: number[] = [];
    info.identifiers.forEach((id, i) => {
      if (id != null && link.hasRow(id)) out.push(i);
    });
    return out;
  });
  const seqTooltip = $derived.by(() => {
    const ids = info?.identifiers;
    if (!ids) return undefined;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (params: any) => {
      const p = Array.isArray(params) ? params[0] : params;
      const i = p?.dataIndex ?? 0;
      return `${ids[i] ?? i + 1}<br/>${column}: ${fmtNum(p?.value)}`;
    };
  });

  // When the selected column changes, preview the transform already applied to it
  // in the draft spec (so e.g. a log-transformed variable shows transformed).
  $effect(() => {
    void column;
    transform = appliedTransform;
  });

  $effect(() => {
    const ds = datasetId;
    const col = column;
    const f = form;
    const excluded = excludedRows;
    // Raw view shows the original data; the transform is part of the scaled
    // (preprocessed) view, so the table and plots stay consistent per mode.
    const t = f === 'scaled' ? transform : 'none';
    void (async () => {
      try {
        info = await getVariable(ds, col, t, f, excluded);
        error = null;
      } catch (e) {
        error = (e as Error).message;
      }
    })();
  });

  function fmt(value: number | null): string {
    if (value === null) return '—';
    return Number(value).toPrecision(4);
  }
</script>

<div class="inspector" data-testid="inspector">
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

      {#if info.histogram_counts.length}
        <h4>Frequency</h4>
        <div data-testid="hist-chart">
          <Histogram counts={info.histogram_counts} edges={info.histogram_edges} height="200px" />
        </div>
      {/if}
      <h4>Sequence</h4>
      <LinePlot
        series={[{ values: info.sequence }]}
        labels={seqLabels}
        xName={seqLabels ? '' : 'order'}
        highlight={seqHighlight}
        tooltipFormatter={seqTooltip}
        height="200px"
      />
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

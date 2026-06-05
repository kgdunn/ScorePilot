<script lang="ts">
  import { page } from '$app/stores';
  import { getModel, type ModelDetail, type ModelDiagnostics } from '$lib/api';
  import { showError } from '$lib/toast.svelte';
  import { formatDateTime } from '$lib/format';
  import Chart from '$lib/components/Chart.svelte';
  import {
    barWithLimitOption,
    loadingsOption,
    oneComponentOption,
    scoresEllipseOption,
    vipOption,
    type OneAxisKind,
    type ScatterPoint
  } from '$lib/echarts';

  const id = $derived(Number($page.params.id));
  let detail = $state<ModelDetail | null>(null);
  // Chart type for the single-component (1-axis) scores/loadings plots.
  let oneAxisKind = $state<OneAxisKind>('bar');
  // Axis selection for the scores/loadings scatters: a component index, or 'seq'
  // for the data's sequence (observation/variable) order.
  type AxisSel = number | 'seq';
  let scoresX = $state<AxisSel>(0);
  let scoresY = $state<AxisSel>(1);
  let loadingsX = $state<AxisSel>(0);
  let loadingsY = $state<AxisSel>(1);

  $effect(() => {
    const mid = id;
    if (Number.isNaN(mid)) return;
    void (async () => {
      try {
        detail = await getModel(mid);
        // Reset axis pickers to the canonical pair for the loaded model.
        const a = detail.diagnostics?.n_components ?? 0;
        scoresX = 0;
        scoresY = a >= 2 ? 1 : 'seq';
        loadingsX = 0;
        loadingsY = a >= 2 ? 1 : 'seq';
      } catch (e) {
        showError((e as Error).message);
      }
    })();
  });

  function axis(d: ModelDiagnostics, i: number): string {
    const name = d.component_names[i] ?? `PC${i + 1}`;
    // Variance explained is always shown in square brackets, consistently.
    const pct = d.r2_per_component[i] != null ? ` [${(d.r2_per_component[i] * 100).toFixed(1)}%]` : '';
    return `${name}${pct}`;
  }

  function axisName(d: ModelDiagnostics, sel: AxisSel): string {
    return sel === 'seq' ? 'Sequence order' : axis(d, sel);
  }

  /** Options for an axis dropdown: "Seq" first, then each component. */
  function axisOptions(d: ModelDiagnostics): { value: AxisSel; label: string }[] {
    return [
      { value: 'seq', label: 'Seq' },
      ...d.component_names.map((_, c) => ({ value: c as AxisSel, label: axis(d, c) }))
    ];
  }

  function scoreAt(d: ModelDiagnostics, sel: AxisSel, row: number): number {
    return sel === 'seq' ? row + 1 : (d.scores.data[row][sel] ?? 0);
  }

  function loadAt(d: ModelDiagnostics, sel: AxisSel, row: number): number {
    return sel === 'seq' ? row + 1 : (d.x_loadings.data[row][sel] ?? 0);
  }

  // Scores carry SPE and Hotelling's T2 per point so the hover can show them.
  function scorePoints(d: ModelDiagnostics): ScatterPoint[] {
    return d.scores.data.map((_, i) => [
      scoreAt(d, scoresX, i),
      scoreAt(d, scoresY, i),
      d.scores.observation_names[i],
      d.spe[i],
      d.hotellings_t2[i]
    ]);
  }

  function loadingPoints(d: ModelDiagnostics): ScatterPoint[] {
    return d.x_loadings.data.map((_, i) => [
      loadAt(d, loadingsX, i),
      loadAt(d, loadingsY, i),
      d.x_loadings.variable_names[i]
    ]);
  }

  function vipPair(d: ModelDiagnostics): { names: string[]; values: number[] } {
    const names = Object.keys(d.vip);
    return { names, values: names.map((n) => d.vip[n]) };
  }

  function scoreValues(d: ModelDiagnostics): number[] {
    return d.scores.data.map((r) => r[0]);
  }

  function loadingValues(d: ModelDiagnostics): number[] {
    return d.x_loadings.data.map((r) => r[0]);
  }

  function preprocessingSummary(p: Record<string, unknown>): string {
    const x = (p.x_columns as string[] | undefined)?.length ?? 0;
    const y = (p.y_columns as string[] | undefined)?.length ?? 0;
    const tr = Object.keys((p.transforms as Record<string, unknown>) ?? {}).length;
    const exr = (p.excluded_rows as number[] | undefined)?.length ?? 0;
    const exc = (p.excluded_columns as string[] | undefined)?.length ?? 0;
    return `X: ${x}, Y: ${y}, transforms: ${tr}, excluded rows: ${exr}, excluded cols: ${exc}, scaling: ${p.default_scaling ?? '—'}`;
  }

  const pageTitle = $derived(
    detail ? `${detail.summary.name ?? `Model ${detail.summary.id}`} · ScorePilot` : 'ScorePilot'
  );
</script>

<svelte:head><title>{pageTitle}</title></svelte:head>

<main>
  <p class="nav"><a href="/models">← Hangar</a></p>

  {#if detail}
    {@const s = detail.summary}
    <h1>
      <span class="kind {s.kind.toLowerCase()}">{s.kind}</span>
      {s.name ?? `Model ${s.id}`}
    </h1>

    <section class="logbook">
      <h2>Logbook</h2>
      <dl>
        <dt>Components</dt><dd>{s.n_components}</dd>
        <dt>Created</dt><dd>{formatDateTime(s.created_at)}</dd>
        <dt>Preprocessing</dt><dd>{preprocessingSummary(detail.preprocessing)}</dd>
        <dt>Lineage</dt>
        <dd>
          {#each detail.lineage as anc, i (anc.id)}
            {#if i > 0}<span class="sep">→</span>{/if}
            {#if anc.id === s.id}
              <strong>{anc.name ?? `#${anc.id}`}</strong>
            {:else}
              <a href={`/models/${anc.id}`}>{anc.name ?? `#${anc.id}`}</a>
            {/if}
          {/each}
        </dd>
      </dl>
      {#if s.dataset_id}
        <a class="explore-link" href={`/datasets/${s.dataset_id}`}>Open dataset to build a variant →</a>
      {/if}
    </section>

    {#if detail.diagnostics}
      {@const d = detail.diagnostics}
      {@const oneComponent = d.n_components < 2}
      <section class="diagnostics" data-testid="diagnostics">
        {#if oneComponent}
          <div class="chart-kind">
            <label>
              Chart type
              <select bind:value={oneAxisKind}>
                <option value="bar">Bar</option>
                <option value="line">Line</option>
                <option value="scatter">Scatter</option>
              </select>
            </label>
            <span class="hint">This model has one component, so scores and loadings are shown on a single axis.</span>
          </div>
        {/if}
        <div class="grid2">
          <div class="card">
            <h3>Scores (with T² limit)</h3>
            {#if oneComponent}
              <Chart option={oneComponentOption(d.scores.observation_names, scoreValues(d), axis(d, 0), oneAxisKind, 'observation')} />
            {:else}
              {@const canonical = scoresX === 0 && scoresY === 1}
              <div class="axis-pick">
                <label>X
                  <select bind:value={scoresX}>
                    {#each axisOptions(d) as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
                  </select>
                </label>
                <label>Y
                  <select bind:value={scoresY}>
                    {#each axisOptions(d) as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
                  </select>
                </label>
              </div>
              <Chart
                option={scoresEllipseOption(
                  scorePoints(d),
                  canonical ? d.ellipse_x : [],
                  canonical ? d.ellipse_y : [],
                  axisName(d, scoresX),
                  axisName(d, scoresY)
                )}
              />
            {/if}
          </div>
          <div class="card">
            <h3>Loadings</h3>
            {#if oneComponent}
              <Chart option={oneComponentOption(d.x_loadings.variable_names, loadingValues(d), axis(d, 0), oneAxisKind, 'variable')} />
            {:else}
              <div class="axis-pick">
                <label>X
                  <select bind:value={loadingsX}>
                    {#each axisOptions(d) as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
                  </select>
                </label>
                <label>Y
                  <select bind:value={loadingsY}>
                    {#each axisOptions(d) as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
                  </select>
                </label>
              </div>
              <Chart option={loadingsOption(loadingPoints(d), axisName(d, loadingsX), axisName(d, loadingsY))} />
            {/if}
          </div>
          <div class="card">
            <h3>Hotelling's T²</h3>
            <Chart option={barWithLimitOption(d.scores.observation_names, d.hotellings_t2, d.t2_limit, 'T²')} />
          </div>
          <div class="card">
            <h3>SPE (DModX)</h3>
            <Chart option={barWithLimitOption(d.scores.observation_names, d.spe, d.spe_limit, 'SPE')} />
          </div>
          <div class="card wide">
            <h3>VIP</h3>
            <Chart option={vipOption(vipPair(d).names, vipPair(d).values)} height="260px" />
          </div>
        </div>
      </section>
    {:else}
      <p class="hint">
        Diagnostics are unavailable because the source dataset is no longer loaded.
        Re-import the dataset to view plots.
      </p>
    {/if}
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
    max-width: 80rem;
    margin: 1.5rem auto;
    padding: 0 1.5rem;
  }
  .nav {
    font-size: 0.85rem;
  }
  .kind {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    color: #fff;
    font-size: 0.8rem;
    vertical-align: middle;
  }
  .kind.pca {
    background: #2b6cb0;
  }
  .kind.pls {
    background: #2f855a;
  }
  .logbook {
    background: #fff;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
  }
  .logbook h2 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }
  dl {
    display: grid;
    grid-template-columns: 8rem 1fr;
    gap: 0.25rem 1rem;
    margin: 0;
    font-size: 0.88rem;
  }
  dt {
    color: #666;
    font-weight: 600;
  }
  dd {
    margin: 0;
  }
  .sep {
    color: #aaa;
    margin: 0 0.3rem;
  }
  .explore-link {
    display: inline-block;
    margin-top: 0.5rem;
    font-size: 0.85rem;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }
  .chart-kind {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 0.75rem;
    font-size: 0.85rem;
  }
  .chart-kind label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .chart-kind select {
    padding: 0.2rem;
  }
  .axis-pick {
    display: flex;
    gap: 1rem;
    align-items: center;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }
  .axis-pick label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .axis-pick select {
    padding: 0.2rem;
  }
  .card {
    background: #fff;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    padding: 0.5rem 0.75rem;
  }
  .card.wide {
    grid-column: 1 / -1;
  }
  .card h3 {
    margin: 0 0 0.3rem;
    font-size: 0.9rem;
  }
  .hint {
    color: #777;
  }
  /* On narrow screens, stack the diagnostic cards in a single column. */
  @media (max-width: 900px) {
    main {
      margin: 1rem auto;
      padding: 0 0.75rem;
    }
    .grid2 {
      grid-template-columns: 1fr;
    }
    dl {
      grid-template-columns: 6rem 1fr;
    }
  }
</style>

<script lang="ts">
  import { page } from '$app/stores';
  import { getModel, type ModelDetail, type ModelDiagnostics } from '$lib/api';
  import Chart from '$lib/components/Chart.svelte';
  import {
    barWithLimitOption,
    loadingsOption,
    scoresEllipseOption,
    vipOption,
    type ScorePoint
  } from '$lib/echarts';

  const id = $derived(Number($page.params.id));
  let detail = $state<ModelDetail | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    const mid = id;
    if (Number.isNaN(mid)) return;
    void (async () => {
      try {
        detail = await getModel(mid);
        error = null;
      } catch (e) {
        error = (e as Error).message;
      }
    })();
  });

  function axis(d: ModelDiagnostics, i: number): string {
    const name = d.component_names[i] ?? `PC${i + 1}`;
    const pct = d.r2_per_component[i] != null ? ` (${(d.r2_per_component[i] * 100).toFixed(1)}%)` : '';
    return `${name}${pct}`;
  }

  function scorePoints(d: ModelDiagnostics): ScorePoint[] {
    return d.scores.data.map((r, i) => [r[0], r[1] ?? 0, d.scores.observation_names[i]]);
  }

  function loadingPoints(d: ModelDiagnostics): ScorePoint[] {
    return d.x_loadings.data.map((r, i) => [r[0], r[1] ?? 0, d.x_loadings.variable_names[i]]);
  }

  function vipPair(d: ModelDiagnostics): { names: string[]; values: number[] } {
    const names = Object.keys(d.vip);
    return { names, values: names.map((n) => d.vip[n]) };
  }

  function preprocessingSummary(p: Record<string, unknown>): string {
    const x = (p.x_columns as string[] | undefined)?.length ?? 0;
    const y = (p.y_columns as string[] | undefined)?.length ?? 0;
    const tr = Object.keys((p.transforms as Record<string, unknown>) ?? {}).length;
    const exr = (p.excluded_rows as number[] | undefined)?.length ?? 0;
    const exc = (p.excluded_columns as string[] | undefined)?.length ?? 0;
    return `X: ${x}, Y: ${y}, transforms: ${tr}, excluded rows: ${exr}, excluded cols: ${exc}, scaling: ${p.default_scaling ?? '—'}`;
  }
</script>

<main>
  <p class="nav"><a href="/models">← Hangar</a></p>
  {#if error}<p class="error">{error}</p>{/if}

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
        <dt>Dataset</dt><dd>{s.dataset_id ?? '—'}</dd>
        <dt>Created</dt><dd>{new Date(s.created_at).toLocaleString()}</dd>
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
      <section class="diagnostics" data-testid="diagnostics">
        <div class="grid2">
          <div class="card">
            <h3>Scores (with T² limit)</h3>
            <Chart option={scoresEllipseOption(scorePoints(d), d.ellipse_x, d.ellipse_y, axis(d, 0), axis(d, 1))} />
          </div>
          <div class="card">
            <h3>Loadings</h3>
            <Chart option={loadingsOption(loadingPoints(d), axis(d, 0), axis(d, 1))} />
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
  .error {
    color: #b3261e;
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

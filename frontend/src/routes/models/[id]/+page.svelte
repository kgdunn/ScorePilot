<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    createVariant,
    getContributions,
    getCrossValidation,
    getModel,
    updateModelComponents,
    type Contributions,
    type CrossValidation,
    type CvScheme,
    type ModelDetail,
    type ModelDiagnostics,
    type SelectionRule
  } from '$lib/api';
  import { showError } from '$lib/toast.svelte';
  import { formatDateTime } from '$lib/format';
  import ComponentExplorer from '$lib/components/ComponentExplorer.svelte';
  import {
    BarPlot,
    LinePlot,
    ScatterPlot,
    createLinkGroup,
    fmtNum,
    type AxisControl,
    type ChartActivation,
    type LimitLine,
    type OverlayLine,
    type PlotPoint
  } from '$lib/plots';
  import ContributionModal from '$lib/components/ContributionModal.svelte';
  import VariableRawModal from '$lib/components/VariableRawModal.svelte';

  /** Chart type for the single-component (1-axis) scores/loadings plots. */
  type OneAxisKind = 'bar' | 'line' | 'scatter';
  /** A score point carries SPE / T² so the hover can show them. */
  type ScorePt = PlotPoint & { spe?: number; t2?: number };
  /** Grey dashed baseline at y = 0 for the single-component plots. */
  const BASELINE: LimitLine = { value: 0, color: '#bbb', dashed: true, label: '' };

  const id = $derived(Number($page.params.id));
  let detail = $state<ModelDetail | null>(null);
  let crossValidation = $state<CrossValidation | null>(null);
  let oneAxisKind = $state<OneAxisKind>('bar');

  // Issue #63: the component explorer scrubs the count and applies it live (no
  // Apply button). Diagnostics for each count are cached in the browser, so
  // revisiting a count - e.g. stepping back down - is instant; only a brand-new
  // (higher) count computes. Neighbours are prefetched so stepping feels instant
  // both ways. The chosen count is persisted in the background (debounced).
  let components = $state(1);
  let saving = $state(false);
  let cvMax = $state(1);
  // Component-selection controls (full rule selector). Defaults track the model
  // kind; changing either re-runs cross-validation server-side.
  let selectionRule = $state<SelectionRule>('min');
  let cvScheme = $state<CvScheme>('ekf');
  let displayDiag = $state<ModelDiagnostics | null>(null);
  let diagCache = new Map<number, ModelDiagnostics>();
  const diag = $derived<ModelDiagnostics | null>(displayDiag);
  // Shared brushing context for this model's plots: a selection made in the
  // scores plot (rows) or loadings plot (columns) is highlighted everywhere.
  const link = createLinkGroup();

  // Issue #73: encode a per-observation metric onto the scores points' colour
  // and/or size, to surface outliers at a glance.
  type Channel = 'none' | 'spe' | 't2';
  let colorBy = $state<Channel>('none');
  let sizeBy = $state<Channel>('none');

  const channelLabel = (ch: Channel): string =>
    ch === 'spe' ? 'SPE' : ch === 't2' ? "Hotelling's T²" : '';
  function metricArray(d: ModelDiagnostics, ch: Channel): number[] | null {
    if (ch === 'spe') return d.spe;
    if (ch === 't2') return d.hotellings_t2;
    return null;
  }
  function extent(xs: number[]): [number, number] {
    let lo = Infinity;
    let hi = -Infinity;
    for (const x of xs) {
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
    return [lo, hi];
  }
  const norm = (v: number, lo: number, hi: number): number => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
  // Blue (#2b6cb0) -> red (#c53030) ramp; matches the CSS gradient in the legend.
  function ramp(t: number): string {
    const a = [43, 108, 176];
    const b = [197, 48, 48];
    const c = a.map((av, i) => Math.round(av + (b[i] - av) * Math.max(0, Math.min(1, t))));
    return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  }
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
        crossValidation = null;
        link.reset();
        diagCache = new Map();
        detail = await getModel(mid);
        const dg = detail.diagnostics;
        const a = dg?.n_components ?? 0;
        components = detail.summary.n_components;
        displayDiag = dg;
        if (dg) diagCache.set(components, dg);
        // Reset axis pickers to the canonical pair for the loaded model.
        scoresX = 0;
        scoresY = a >= 2 ? 1 : 'seq';
        loadingsX = 0;
        loadingsY = a >= 2 ? 1 : 'seq';
        // Cross-validation is fetched by the dedicated effect below (so it also
        // re-runs when the selection rule / scheme change). Here we just set the
        // curve ceiling and reset the controls to this model kind's defaults.
        // Extend the curve past the current count (bounded by rank) so the
        // explorer can show the value of adding more components.
        if (dg) {
          const kVars = dg.x_loadings.variable_names.length;
          const nObs = dg.scores.data.length;
          cvMax = Math.max(a, Math.min(20, kVars, Math.max(1, nObs - 1)));
          selectionRule = detail.summary.kind === 'PLS' ? '1se' : 'min';
          cvScheme = 'ekf';
        }
      } catch (e) {
        showError((e as Error).message);
      }
    })();
  });

  // Re-run cross-validation whenever the loaded model, its component ceiling, or
  // the selection controls change. Kept separate from diagnostics so a CV
  // failure (e.g. too few rows, collinear data) never blocks the rest of the page.
  $effect(() => {
    const mid = id;
    const max = cvMax;
    const rule = selectionRule;
    const scheme = cvScheme;
    // Only fetch once the detail for *this* model has loaded, to avoid a stale
    // fetch with the previous model's ceiling while navigating.
    if (!detail || detail.summary.id !== mid || max < 1) return;
    void (async () => {
      try {
        crossValidation = await getCrossValidation(mid, {
          maxComponents: max,
          selectionRule: rule,
          cvScheme: scheme
        });
      } catch {
        crossValidation = null;
      }
    })();
  });

  // Show the diagnostics for the current count: instant from cache, otherwise
  // fetch (the only "going up to a new count" delay) and cache it.
  $effect(() => {
    const mid = id;
    const k = components;
    if (!detail || Number.isNaN(mid)) return;
    const cached = diagCache.get(k);
    if (cached) {
      if (displayDiag !== cached) displayDiag = cached;
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      void getModel(mid, k)
        .then((d) => {
          if (cancelled || !d.diagnostics) return;
          if (!diagCache.has(k)) diagCache.set(k, d.diagnostics);
          if (components === k) displayDiag = diagCache.get(k) ?? d.diagnostics;
        })
        .catch(() => {});
    }, 110);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  });

  // Warm the neighbouring counts in the background so stepping is instant both
  // ways (the next step down is already cached).
  $effect(() => {
    const mid = id;
    const k = components;
    if (!detail || Number.isNaN(mid)) return;
    const timer = setTimeout(() => {
      for (const n of [k - 1, k + 1]) {
        if (n >= 1 && n <= cvMax && !diagCache.has(n)) {
          void getModel(mid, n)
            .then((d) => {
              if (d.diagnostics && !diagCache.has(n)) diagCache.set(n, d.diagnostics);
            })
            .catch(() => {});
        }
      }
    }, 300);
    return () => clearTimeout(timer);
  });

  // Persist the chosen count in the background (debounced). Cache is write-once
  // per count, so this never replaces what's on screen - no flash on settle.
  $effect(() => {
    const mid = id;
    const k = components;
    const stored = detail?.summary.n_components;
    if (!detail || stored == null || Number.isNaN(mid) || k === stored) return;
    let cancelled = false;
    saving = true;
    const timer = setTimeout(() => {
      void updateModelComponents(mid, k)
        .then((d) => {
          if (cancelled) return;
          if (d.diagnostics && !diagCache.has(k)) diagCache.set(k, d.diagnostics);
          detail = d;
        })
        .catch((e) => showError((e as Error).message))
        .finally(() => {
          if (!cancelled) saving = false;
        });
    }, 700);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
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

  const selToStr = (s: AxisSel): string => (s === 'seq' ? 'seq' : String(s));
  const strToSel = (v: string): AxisSel => (v === 'seq' ? 'seq' : Number(v));

  /** Axis drop-down wiring for a scatter: "Seq" first, then each component. */
  function axisControl(
    d: ModelDiagnostics,
    x: AxisSel,
    y: AxisSel,
    set: (x: AxisSel, y: AxisSel) => void
  ): AxisControl {
    const options = [
      { value: 'seq', label: 'Seq' },
      ...d.component_names.map((_, c) => ({ value: selToStr(c), label: axis(d, c) }))
    ];
    return {
      options,
      x: selToStr(x),
      y: selToStr(y),
      onchange: (nx, ny) => set(strToSel(nx), strToSel(ny))
    };
  }

  function scoreAt(d: ModelDiagnostics, sel: AxisSel, row: number): number {
    return sel === 'seq' ? row + 1 : (d.scores.data[row][sel] ?? 0);
  }

  function loadAt(d: ModelDiagnostics, sel: AxisSel, row: number): number {
    return sel === 'seq' ? row + 1 : (d.x_loadings.data[row][sel] ?? 0);
  }

  // Scores carry SPE and Hotelling's T2 per point so the hover can show them;
  // each point is keyed by its observation name for row-wise linking.
  function scorePoints(d: ModelDiagnostics): ScorePt[] {
    const colorVals = metricArray(d, colorBy);
    const sizeVals = metricArray(d, sizeBy);
    const cExt = colorVals ? extent(colorVals) : null;
    const sExt = sizeVals ? extent(sizeVals) : null;
    return d.scores.data.map((_, i) => {
      const pt: ScorePt = {
        rowId: d.scores.observation_names[i],
        label: d.scores.observation_names[i],
        x: scoreAt(d, scoresX, i),
        y: scoreAt(d, scoresY, i),
        spe: d.spe[i],
        t2: d.hotellings_t2[i]
      };
      if (colorVals && cExt) pt.color = ramp(norm(colorVals[i], cExt[0], cExt[1]));
      if (sizeVals && sExt) pt.size = 8 + 16 * norm(sizeVals[i], sExt[0], sExt[1]);
      return pt;
    });
  }

  function loadingPoints(d: ModelDiagnostics): PlotPoint[] {
    return d.x_loadings.data.map((_, i) => ({
      colId: d.x_loadings.variable_names[i],
      label: d.x_loadings.variable_names[i],
      x: loadAt(d, loadingsX, i),
      y: loadAt(d, loadingsY, i)
    }));
  }

  // One-component plots: one value per observation / variable on a category axis.
  function scoreBars(d: ModelDiagnostics): PlotPoint[] {
    return d.scores.observation_names.map((name, i) => ({
      rowId: name,
      x: name,
      y: d.scores.data[i][0]
    }));
  }

  function loadingBars(d: ModelDiagnostics): PlotPoint[] {
    return d.x_loadings.variable_names.map((name, i) => ({
      colId: name,
      x: name,
      y: d.x_loadings.data[i][0]
    }));
  }

  function barsFrom(names: string[], values: number[], dim: 'row' | 'col'): PlotPoint[] {
    return names.map((name, i) => ({
      [dim === 'row' ? 'rowId' : 'colId']: name,
      x: name,
      y: values[i]
    }));
  }

  function vipPoints(d: ModelDiagnostics): PlotPoint[] {
    const names = Object.keys(d.vip);
    return barsFrom(names, names.map((n) => d.vip[n]), 'col');
  }

  function ellipseOverlay(d: ModelDiagnostics): OverlayLine[] {
    if (!d.ellipse_x?.length) return [];
    return [{ points: d.ellipse_x.map((x, i): [number, number] => [x, d.ellipse_y[i]]), color: '#c53030', dashed: true }];
  }

  const scoreTooltip = (d: ModelDiagnostics) => (p: PlotPoint) => {
    const q = p as ScorePt;
    let html = `${p.label ?? ''}<br/>${axisName(d, scoresX)}: ${fmtNum(p.x as number)}<br/>${axisName(d, scoresY)}: ${fmtNum(p.y)}`;
    if (q.spe != null) html += `<br/>SPE: ${fmtNum(q.spe)}`;
    if (q.t2 != null) html += `<br/>Hotelling's T²: ${fmtNum(q.t2)}`;
    return html;
  };

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

  // Contribution-plot modal: opened by double-click / long-press on a score,
  // T2, or SPE point. Scores explain outlyingness via T2; SPE bars via SPE.
  let contribution = $state<Contributions | null>(null);
  let contributionMetric = $state<'t2' | 'spe'>('t2');
  // Raw-data modal: opened by clicking a bar in the contribution plot.
  let rawVariable = $state<string | null>(null);

  async function openContribution(observation: number, metric: 't2' | 'spe') {
    try {
      contribution = await getContributions(id, observation);
      contributionMetric = metric;
    } catch (e) {
      showError((e as Error).message);
    }
  }

  const onScoreActivate = (a: ChartActivation) => openContribution(a.dataIndex, 't2');
  const onT2Activate = (a: ChartActivation) => openContribution(a.dataIndex, 't2');
  const onSpeActivate = (a: ChartActivation) => openContribution(a.dataIndex, 'spe');

  // Issue #62: double-click / long-press a loadings point opens that variable's
  // raw data; the selected rows carry over and stay highlighted there.
  function openVariableRaw(d: ModelDiagnostics, dataIndex: number): void {
    rawVariable = d.x_loadings.variable_names[dataIndex];
  }

  // Issue #72: act on the current selection by forking a child variant (exclude
  // the selected rows/variables, or keep only the selected rows), then open it.
  let variantBusy = $state(false);
  async function makeVariant(mode: 'exclude' | 'keep', useRows: boolean, useCols: boolean) {
    if (variantBusy) return;
    variantBusy = true;
    try {
      const created = await createVariant(id, {
        mode,
        observations: useRows ? [...link.rows] : [],
        variables: useCols ? [...link.cols] : []
      });
      link.reset();
      await goto(`/models/${created.summary.id}`);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      variantBusy = false;
    }
  }
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

    {#if diag}
      {@const d = diag}
      {@const oneComponent = d.n_components < 2}
      <section class="diagnostics" data-testid="diagnostics">
        <ComponentExplorer
          bind:components
          max={cvMax}
          recommended={crossValidation?.recommended ?? null}
          cv={crossValidation}
          kind={d.kind}
          bind:selectionRule
          bind:cvScheme
          {saving}
        />
        {#if crossValidation}
          {@const cv = crossValidation}
          <div class="card wide r2card">
            <h3>R² and cross-validated R² (Q²) per component</h3>
            <p class="hint">
              R² is the in-sample fit of {cv.target}; Q² is its cross-validated
              ({cv.n_splits}-fold) prediction, with a shaded ±1 SE band. The blue marker
              tracks the slider above; the <strong>{cv.selection_rule}</strong> rule recommends
              <strong>{cv.recommended}</strong>
              component{cv.recommended === 1 ? '' : 's'}
              {#if cv.recommended_vote_share != null}
                (chosen in {Math.round(cv.recommended_vote_share * 100)}% of {cv.n_repeats} repeats{#if cv.recommended_is_stable === false}, <span class="unstable">unstable</span>{/if})
              {/if}.
            </p>
            <LinePlot
              series={[
                { name: `R² (${cv.target})`, values: cv.r2, color: '#2b6cb0' },
                {
                  name: `Q² (${cv.target}, cross-validated)`,
                  values: cv.q2,
                  color: '#2f855a',
                  band: cv.q2_se
                }
              ]}
              labels={cv.component_numbers}
              xName="components"
              yName="cumulative fraction"
              legend
              xMarks={[
                { value: String(components), label: `${components}`, color: '#2b6cb0' },
                ...(cv.recommended !== components
                  ? [{ value: String(cv.recommended), label: 'rec', color: '#dd6b20', dashed: true }]
                  : [])
              ]}
              height="260px"
            />
            <table class="r2-table">
              <thead>
                <tr>
                  <th>Component</th>
                  <th>R²</th>
                  <th>R² (cum.)</th>
                  <th>Q²</th>
                  <th>Q² (cum.)</th>
                </tr>
              </thead>
              <tbody>
                {#each cv.component_numbers as comp, i (comp)}
                  <tr class:recommended={comp === cv.recommended} class:current={comp === components}>
                    <td>{comp}</td>
                    <td>{(cv.r2_per_component[i] * 100).toFixed(1)}%</td>
                    <td>{(cv.r2[i] * 100).toFixed(1)}%</td>
                    <td>{(cv.q2_per_component[i] * 100).toFixed(1)}%</td>
                    <td>{(cv.q2[i] * 100).toFixed(1)}%</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
        <p class="hint">
          Double-click or long-press a point on the scores, T², or SPE plot to see its contribution
          plot. Use the arrow or lasso tools on the scores and loadings plots to select points; the
          selection is highlighted across every plot.
        </p>
        {#if link.size > 0}
          <div class="selection">
            <span>
              <strong>{link.size}</strong> selected
              ({link.rows.size} row{link.rows.size === 1 ? '' : 's'},
              {link.cols.size} column{link.cols.size === 1 ? '' : 's'})
            </span>
            {#if link.rows.size > 0}
              <button type="button" disabled={variantBusy} onclick={() => makeVariant('exclude', true, link.cols.size > 0)}>
                Exclude selected → new variant
              </button>
              <button type="button" disabled={variantBusy} onclick={() => makeVariant('keep', true, false)}>
                Keep only selected rows → new variant
              </button>
            {:else if link.cols.size > 0}
              <button type="button" disabled={variantBusy} onclick={() => makeVariant('exclude', false, true)}>
                Exclude selected variables → new variant
              </button>
            {/if}
            <button type="button" class="clear" onclick={() => link.reset()}>Clear</button>
          </div>
        {/if}
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
              <BarPlot
                points={scoreBars(d)}
                kind={oneAxisKind}
                yName={axis(d, 0)}
                xName="observation"
                limits={[BASELINE]}
                {link}
                linkBy="row"
                onactivate={onScoreActivate}
              />
            {:else}
              {@const canonical = scoresX === 0 && scoresY === 1}
              <div class="encode">
                <label>Color by
                  <select data-testid="color-by" bind:value={colorBy}>
                    <option value="none">None</option>
                    <option value="spe">SPE</option>
                    <option value="t2">Hotelling's T²</option>
                  </select>
                </label>
                <label>Size by
                  <select data-testid="size-by" bind:value={sizeBy}>
                    <option value="none">None</option>
                    <option value="spe">SPE</option>
                    <option value="t2">Hotelling's T²</option>
                  </select>
                </label>
                {#if colorBy !== 'none'}
                  {@const ext = extent(metricArray(d, colorBy) ?? [0, 1])}
                  <span class="legend">
                    {channelLabel(colorBy)}: {fmtNum(ext[0])}
                    <span class="ramp"></span>
                    {fmtNum(ext[1])}
                  </span>
                {/if}
              </div>
              <ScatterPlot
                points={scorePoints(d)}
                xName={axisName(d, scoresX)}
                yName={axisName(d, scoresY)}
                overlays={canonical ? ellipseOverlay(d) : []}
                axes={axisControl(d, scoresX, scoresY, (x, y) => { scoresX = x; scoresY = y; })}
                tooltipHtml={scoreTooltip(d)}
                {link}
                linkBy="row"
                selectable
                onactivate={onScoreActivate}
              />
            {/if}
          </div>
          <div class="card">
            <h3>Loadings</h3>
            {#if oneComponent}
              <BarPlot
                points={loadingBars(d)}
                kind={oneAxisKind}
                yName={axis(d, 0)}
                xName="variable"
                limits={[BASELINE]}
                {link}
                linkBy="col"
                onactivate={(a) => openVariableRaw(d, a.dataIndex)}
              />
            {:else}
              <ScatterPlot
                points={loadingPoints(d)}
                xName={axisName(d, loadingsX)}
                yName={axisName(d, loadingsY)}
                symbolSize={9}
                axes={axisControl(d, loadingsX, loadingsY, (x, y) => { loadingsX = x; loadingsY = y; })}
                {link}
                linkBy="col"
                selectable
                onactivate={(a) => openVariableRaw(d, a.dataIndex)}
              />
            {/if}
          </div>
          <div class="card">
            <h3>Hotelling's T²</h3>
            <BarPlot
              points={barsFrom(d.scores.observation_names, d.hotellings_t2, 'row')}
              yName="T²"
              limits={[{ value: d.t2_limit, label: `limit ${fmtNum(d.t2_limit)}` }]}
              {link}
              linkBy="row"
              onactivate={onT2Activate}
            />
          </div>
          <div class="card">
            <h3>SPE (DModX)</h3>
            <BarPlot
              points={barsFrom(d.scores.observation_names, d.spe, 'row')}
              yName="SPE"
              limits={[{ value: d.spe_limit, label: `limit ${fmtNum(d.spe_limit)}` }]}
              {link}
              linkBy="row"
              onactivate={onSpeActivate}
            />
          </div>
          <div class="card wide">
            <h3>VIP</h3>
            <BarPlot
              points={vipPoints(d)}
              yName="VIP"
              color="#805ad5"
              limits={[{ value: 1, label: 'VIP 1', dashed: true }]}
              {link}
              linkBy="col"
              height="260px"
            />
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

{#if contribution}
  <ContributionModal
    contributions={contribution}
    metric={contributionMetric}
    {link}
    onclose={() => (contribution = null)}
    onVariableClick={(v) => (rawVariable = v)}
  />
{/if}

{#if rawVariable && detail?.summary.dataset_id}
  <VariableRawModal
    datasetId={detail.summary.dataset_id}
    column={rawVariable}
    {link}
    onclose={() => (rawVariable = null)}
  />
{/if}

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
  .encode {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
    font-size: 0.82rem;
    color: #555;
  }
  .encode label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .encode select {
    padding: 0.15rem;
  }
  .encode .legend {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .encode .ramp {
    display: inline-block;
    width: 70px;
    height: 10px;
    border-radius: 2px;
    /* Matches ramp() in the script: blue -> red. */
    background: linear-gradient(to right, #2b6cb0, #c53030);
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
  .selection {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    font-size: 0.85rem;
    margin: 0 0 0.75rem;
  }
  .selection button {
    padding: 0.2rem 0.7rem;
    border: 1px solid #2b6cb0;
    background: #2b6cb0;
    color: #fff;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.8rem;
  }
  .selection button:hover {
    background: #245a96;
  }
  .selection button:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .selection button.clear {
    border-color: #c53030;
    background: #fff;
    color: #c53030;
  }
  .selection button.clear:hover {
    background: #c53030;
    color: #fff;
  }
  .unstable {
    color: #c05621;
    font-weight: 600;
  }
  .r2-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-top: 0.5rem;
  }
  .r2-table th,
  .r2-table td {
    text-align: right;
    padding: 3px 8px;
    border-bottom: 1px solid #eee;
  }
  .r2-table th:first-child,
  .r2-table td:first-child {
    text-align: left;
  }
  .r2-table th {
    color: #666;
    font-weight: 600;
  }
  .r2-table tr.recommended {
    background: #fffaf0;
    font-weight: 600;
  }
  /* The component currently shown in the explorer / slider. */
  .r2-table tr.current {
    background: #e8f1fb;
    box-shadow: inset 3px 0 0 #2b6cb0;
  }
  .r2-table tr.current.recommended {
    background: #eef2f0;
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

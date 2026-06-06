<script lang="ts">
  import type { ECharts } from 'echarts';
  import PlotChart, { type ChartActivation } from './PlotChart.svelte';
  import { scatterOption } from './options';
  import type { LinkGroup } from './link.svelte';
  import type { AxisControl, LinkDim, OverlayLine, PlotPoint } from './plot-types';

  type SelectMode = 'default' | 'arrow' | 'lasso';

  interface Props {
    points: PlotPoint[];
    xName?: string;
    yName?: string;
    height?: string;
    /** Shared brushing context; selections read/write here. */
    link?: LinkGroup;
    /** Which identity dimension this plot selects on. */
    linkBy?: LinkDim;
    /** Show the default / arrow / lasso selection toolbar. */
    selectable?: boolean;
    symbolSize?: number;
    showLabels?: boolean;
    showOrigin?: boolean;
    overlays?: OverlayLine[];
    /** Optional axis drop-downs rendered above the plot. */
    axes?: AxisControl;
    tooltipHtml?: (p: PlotPoint) => string;
    onactivate?: (a: ChartActivation) => void;
  }
  let {
    points,
    xName = '',
    yName = '',
    height = '320px',
    link,
    linkBy = 'row',
    selectable = false,
    symbolSize = 11,
    showLabels = true,
    showOrigin = true,
    overlays = [],
    axes,
    tooltipHtml,
    onactivate
  }: Props = $props();

  let mode = $state<SelectMode>('default');
  let chart: ECharts | null = null;

  const option = $derived(
    scatterOption({
      points,
      xName,
      yName,
      symbolSize,
      showLabels,
      showOrigin,
      overlays,
      selectedRows: link?.rows,
      selectedCols: link?.cols,
      linkBy,
      brushable: selectable,
      tooltipHtml
    })
  );

  function selectIndices(idxs: number[], toggle = false): void {
    if (!link) return;
    for (const i of idxs) {
      const p = points[i];
      if (!p) continue;
      const onCol = linkBy === 'col' || (linkBy === 'both' && p.rowId == null);
      const key = onCol ? p.colId : p.rowId;
      if (key == null) continue;
      if (toggle) (onCol ? link.toggleCol(key) : link.toggleRow(key));
      else (onCol ? link.addCols([key]) : link.addRows([key]));
    }
  }

  // The most recent enclosed points while a lasso is being drawn. ECharts
  // auto-closes the polygon (last vertex -> first), so even a partial ring is a
  // closed shape - forgiving on touch, where you can never trace exactly back to
  // the start. Committed on release (brushEnd), per "select by the end".
  let lassoSelected: number[] = [];

  function onReady(c: ECharts): void {
    chart = c;
    // Arrow mode: single click toggles a point's membership.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    c.on('click', (p: any) => {
      if (mode !== 'arrow' || p?.componentType !== 'series' || p.seriesIndex !== 0) return;
      if (p.dataIndex != null) selectIndices([p.dataIndex], true);
    });
    // Track the enclosed points as the lasso is drawn. ECharts emits this on
    // every move (it does not emit a final one on mouse-up), so the last value
    // here is the closed-polygon selection at release.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    c.on('brushSelected', (params: any) => {
      const area = (params.batch ?? [])[0];
      const hit = (area?.selected ?? []).find((s: { seriesIndex: number }) => s.seriesIndex === 0);
      lassoSelected = hit?.dataIndex ?? [];
    });
    // On release, commit whatever the closed loop enclosed, then wipe the
    // rubber-band so only the red-square markers remain.
    c.on('brushEnd', () => {
      if (lassoSelected.length) selectIndices(lassoSelected);
      lassoSelected = [];
      c.dispatchAction({ type: 'brush', command: 'clear', areas: [] });
    });
  }

  // Toggle ECharts' global brush cursor to match the chosen mode.
  $effect(() => {
    if (!chart || !selectable) return;
    if (mode === 'lasso') {
      chart.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'brush',
        brushOption: { brushType: 'polygon', brushMode: 'multiple' }
      });
    } else {
      chart.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: false } });
      chart.dispatchAction({ type: 'brush', command: 'clear', areas: [] });
    }
  });
</script>

<div class="scatter">
  {#if axes}
    <div class="axis-pick">
      <label>X
        <select value={axes.x} onchange={(e) => axes.onchange(e.currentTarget.value, axes.y)}>
          {#each axes.options as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
        </select>
      </label>
      <label>Y
        <select value={axes.y} onchange={(e) => axes.onchange(axes.x, e.currentTarget.value)}>
          {#each axes.options as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
        </select>
      </label>
    </div>
  {/if}

  <div class="frame">
    {#if selectable}
      <div class="tools" role="group" aria-label="Selection mode">
        <button
          type="button" class:active={mode === 'default'} title="Pan / zoom"
          aria-pressed={mode === 'default'} onclick={() => (mode = 'default')}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M3 2l10 5-4 1.5L7.5 13z"/></svg>
        </button>
        <button
          type="button" class:active={mode === 'arrow'} title="Click to select points"
          aria-pressed={mode === 'arrow'} onclick={() => (mode = 'arrow')}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="2.5" y="2.5" width="11" height="11" fill="none" stroke="currentColor" stroke-width="1.5" rx="1"/></svg>
        </button>
        <button
          type="button" class:active={mode === 'lasso'} title="Lasso-select points"
          aria-pressed={mode === 'lasso'} onclick={() => (mode = 'lasso')}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 1.5" d="M8 2.5c4 0 5.5 2 5.5 4S11 13 8 13 2.5 9 2.5 6.5 4 2.5 8 2.5z"/></svg>
        </button>
      </div>
    {/if}
    <PlotChart {option} {height} {onactivate} onready={onReady} />
  </div>
</div>

<style>
  .scatter {
    position: relative;
  }
  .frame {
    position: relative;
  }
  .tools {
    position: absolute;
    top: 4px;
    right: 8px;
    z-index: 2;
    display: flex;
    gap: 2px;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 2px;
  }
  .tools button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 22px;
    border: none;
    background: none;
    border-radius: 4px;
    color: #555;
    cursor: pointer;
  }
  .tools button:hover {
    background: #eef2f7;
  }
  .tools button.active {
    background: #2b6cb0;
    color: #fff;
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
</style>

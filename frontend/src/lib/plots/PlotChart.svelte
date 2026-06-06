<script lang="ts">
  import type { ECharts, EChartsOption } from 'echarts';
  import { onDestroy } from 'svelte';
  import { initChart, ZOOM_STEP, zoomedWindow } from './options';

  /** A series-item activation (double-click or long-press) with the data index. */
  export interface ChartActivation {
    dataIndex: number;
    name: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data: any;
  }

  interface Props {
    option: EChartsOption;
    height?: string;
    /** Fired when a data point is double-clicked or long-pressed. */
    onactivate?: (a: ChartActivation) => void;
    /** Fired on a single click of a series item (e.g. a bar). */
    onitemclick?: (a: ChartActivation) => void;
    /** Called once with the ECharts instance, for advanced wiring (brush, events). */
    onready?: (chart: ECharts) => void;
  }
  let { option, height = '320px', onactivate, onitemclick, onready }: Props = $props();

  let el = $state<HTMLDivElement | null>(null);
  let chart: ECharts | null = null;
  let pressTimer: ReturnType<typeof setTimeout> | null = null;

  function cancelPress() {
    if (pressTimer) {
      clearTimeout(pressTimer);
      pressTimer = null;
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function activate(p: any) {
    if (!onactivate || p?.componentType !== 'series' || p.dataIndex == null) return;
    onactivate({ dataIndex: p.dataIndex, name: p.name, data: p.data });
  }

  $effect(() => {
    if (!el) return;
    if (!chart) {
      chart = initChart(el);
      onready?.(chart);
    }
    chart.setOption(option, true);
  });

  // Gentle, cursor-centred wheel zoom. ECharts' built-in wheel zoom is disabled
  // (see options.ts) because it steps far too hard; here each notch nudges the
  // dataZoom window by ZOOM_STEP around the point under the pointer.
  function onWheel(e: WheelEvent) {
    if (!chart || !el) return;
    const opt = chart.getOption() as { dataZoom?: unknown[] };
    if (!opt.dataZoom || opt.dataZoom.length === 0) return;
    // The grid's plotting rectangle, excluding axis-label margins.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const grid = (chart as any).getModel?.()?.getComponent?.('grid', 0);
    const rect = grid?.coordinateSystem?.getRect?.() as
      | { x: number; y: number; width: number; height: number }
      | undefined;
    if (!rect) return;
    const box = el.getBoundingClientRect();
    const px = e.clientX - box.left;
    const py = e.clientY - box.top;
    const cursor = chart.convertFromPixel({ gridIndex: 0 }, [px, py]) as [number, number] | null;
    if (!cursor) return;
    e.preventDefault();
    const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
    const at = (x: number, y: number) =>
      chart!.convertFromPixel({ gridIndex: 0 }, [x, y]) as [number, number];
    const xMin = at(rect.x, rect.y)[0];
    const xMax = at(rect.x + rect.width, rect.y)[0];
    // y pixels grow downward, so the grid bottom maps to the axis minimum.
    const yMax = at(rect.x, rect.y)[1];
    const yMin = at(rect.x, rect.y + rect.height)[1];
    const [nxMin, nxMax] = zoomedWindow(xMin, xMax, cursor[0], factor);
    const [nyMin, nyMax] = zoomedWindow(yMin, yMax, cursor[1], factor);
    chart.dispatchAction({
      type: 'dataZoom',
      batch: [
        { dataZoomIndex: 0, startValue: nxMin, endValue: nxMax },
        { dataZoomIndex: 1, startValue: nyMin, endValue: nyMax }
      ]
    });
  }

  $effect(() => {
    if (!el) return;
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el?.removeEventListener('wheel', onWheel);
  });

  // Wire activation gestures once, after the chart exists: double-click on
  // desktop, and a ~500ms long-press (works for touch) on a series item.
  $effect(() => {
    if (!chart || !onactivate) return;
    const c = chart;
    const onDbl = (p: unknown) => activate(p);
    const onDown = (p: unknown) => {
      cancelPress();
      pressTimer = setTimeout(() => activate(p), 500);
    };
    c.on('dblclick', onDbl);
    c.on('mousedown', onDown);
    c.on('mouseup', cancelPress);
    c.on('globalout', cancelPress);
    c.getZr().on('mousemove', cancelPress);
    return () => {
      c.off('dblclick', onDbl);
      c.off('mousedown', onDown);
      c.off('mouseup', cancelPress);
      c.off('globalout', cancelPress);
      c.getZr().off('mousemove', cancelPress);
      cancelPress();
    };
  });

  // Single-click drill-down on a series item (e.g. a contribution bar).
  $effect(() => {
    if (!chart || !onitemclick) return;
    const c = chart;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const onClick = (p: any) => {
      if (p?.componentType !== 'series' || p.dataIndex == null) return;
      onitemclick({ dataIndex: p.dataIndex, name: p.name, data: p.data });
    };
    c.on('click', onClick);
    return () => c.off('click', onClick);
  });

  $effect(() => {
    if (!el) return;
    const observer = new ResizeObserver(() => chart?.resize());
    observer.observe(el);
    return () => observer.disconnect();
  });

  onDestroy(() => {
    cancelPress();
    chart?.dispose();
    chart = null;
  });
</script>

<div class="chart" bind:this={el} style="height:{height};"></div>

<style>
  /* `position: relative; z-index: 0` makes each chart its own stacking context.
   * ECharts injects its tooltip into this container with an inline
   * `z-index: 9999999`; without a local stacking context that tooltip escapes
   * into the page root and paints over modals (issue #58). Confining it here
   * keeps a background plot's tooltip below any modal, while in-modal charts
   * still show their tooltip above their own canvas. */
  .chart {
    width: 100%;
    position: relative;
    z-index: 0;
  }
</style>

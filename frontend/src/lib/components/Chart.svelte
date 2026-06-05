<script lang="ts">
  import type { ECharts, EChartsOption } from 'echarts';
  import { onDestroy } from 'svelte';
  import { initChart } from '$lib/echarts';

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
  }
  let { option, height = '320px', onactivate }: Props = $props();

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
    chart ??= initChart(el);
    chart.setOption(option, true);
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

  $effect(() => {
    if (!el) return;
    const observer = new ResizeObserver(() => chart?.resize());
    observer.observe(el);
    return () => observer.disconnect();
  });

  onDestroy(() => {
    cancelPress();
    chart?.dispose();
  });
</script>

<div class="chart" bind:this={el} style="height:{height};"></div>

<style>
  .chart {
    width: 100%;
  }
</style>

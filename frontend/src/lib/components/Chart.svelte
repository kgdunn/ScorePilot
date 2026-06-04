<script lang="ts">
  import type { ECharts, EChartsOption } from 'echarts';
  import { onDestroy } from 'svelte';
  import { initChart } from '$lib/echarts';

  interface Props {
    option: EChartsOption;
    height?: string;
  }
  let { option, height = '320px' }: Props = $props();

  let el = $state<HTMLDivElement | null>(null);
  let chart: ECharts | null = null;

  $effect(() => {
    if (!el) return;
    chart ??= initChart(el);
    chart.setOption(option, true);
  });

  $effect(() => {
    if (!el) return;
    const observer = new ResizeObserver(() => chart?.resize());
    observer.observe(el);
    return () => observer.disconnect();
  });

  onDestroy(() => chart?.dispose());
</script>

<div class="chart" bind:this={el} style="height:{height};"></div>

<style>
  .chart {
    width: 100%;
  }
</style>

<script lang="ts">
  import PlotChart from './PlotChart.svelte';
  import { histogramOption } from './options';

  interface Props {
    counts: number[];
    edges: number[];
    height?: string;
  }
  let { counts, edges, height = '320px' }: Props = $props();

  const option = $derived(histogramOption(counts, edges));
</script>

<PlotChart {option} {height} />

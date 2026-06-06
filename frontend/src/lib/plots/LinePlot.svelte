<script lang="ts">
  import PlotChart from './PlotChart.svelte';
  import { lineOption, type LineSeries } from './options';
  import type { LimitLine } from './plot-types';

  interface Props {
    series: LineSeries[];
    /** Category labels for the x-axis; defaults to a 1..n index. */
    labels?: (string | number)[];
    xName?: string;
    yName?: string;
    height?: string;
    showSymbol?: boolean;
    legend?: boolean;
    limits?: LimitLine[];
    /** Indices (in the first series) to mark with a red square - e.g. linked rows. */
    highlight?: number[];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tooltipFormatter?: (params: any) => string;
  }
  let {
    series,
    labels,
    xName = '',
    yName = '',
    height = '320px',
    showSymbol = false,
    legend = false,
    limits = [],
    highlight = [],
    tooltipFormatter
  }: Props = $props();

  const option = $derived(
    lineOption({ series, labels, xName, yName, showSymbol, legend, limits, highlight, tooltipFormatter })
  );
</script>

<PlotChart {option} {height} />

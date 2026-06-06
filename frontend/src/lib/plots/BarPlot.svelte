<script lang="ts">
  import PlotChart, { type ChartActivation } from './PlotChart.svelte';
  import { barOption } from './options';
  import type { LinkGroup } from './link.svelte';
  import type { LimitLine, LinkDim, PlotPoint } from './plot-types';

  interface Props {
    points: PlotPoint[];
    yName?: string;
    xName?: string;
    color?: string;
    height?: string;
    /** Series type: bars (default), or a line / scatter over the same categories. */
    kind?: 'bar' | 'line' | 'scatter';
    limits?: LimitLine[];
    /** Shared brushing context; selected bars are outlined in red. */
    link?: LinkGroup;
    linkBy?: LinkDim;
    onactivate?: (a: ChartActivation) => void;
    onitemclick?: (a: ChartActivation) => void;
  }
  let {
    points,
    yName = '',
    xName = '',
    color,
    height = '320px',
    kind = 'bar',
    limits = [],
    link,
    linkBy = 'row',
    onactivate,
    onitemclick
  }: Props = $props();

  const option = $derived(
    barOption({
      points,
      yName,
      xName,
      color,
      kind,
      limits,
      selectedRows: link?.rows,
      selectedCols: link?.cols,
      linkBy
    })
  );
</script>

<PlotChart {option} {height} {onactivate} {onitemclick} />

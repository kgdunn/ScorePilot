// Public entry point for the standalone, domain-agnostic plotting library.
//
// Feed plots `PlotPoint`s carrying opaque `rowId` / `colId` identities, share a
// `LinkGroup` between them for brushing-and-linking, and style / label through
// props. Depends only on Svelte 5 and ECharts. Copy the `plots/` folder to reuse.
export { default as PlotChart, type ChartActivation } from './PlotChart.svelte';
export { default as ScatterPlot } from './ScatterPlot.svelte';
export { default as BarPlot } from './BarPlot.svelte';
export { default as LinePlot } from './LinePlot.svelte';
export { default as Histogram } from './Histogram.svelte';

export { LinkGroup, createLinkGroup } from './link.svelte';
export { SELECT_BORDER } from './options';
export type { LineSeries } from './options';
export type {
  AxisControl,
  AxisOption,
  LimitLine,
  LinkDim,
  OverlayLine,
  PlotPoint,
  PlotSymbol
} from './plot-types';

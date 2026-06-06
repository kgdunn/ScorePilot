// Internal ECharts option builders and shared style tokens for the plotting
// library. This is the one module that knows about ECharts; the Svelte
// components are thin wrappers around these pure builders. Builders take the
// domain-agnostic `PlotPoint` model (plus link state) and return an
// `EChartsOption`.
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import type { LimitLine, LinkDim, OverlayLine, PlotPoint } from './plot-types';

export function initChart(element: HTMLElement): echarts.ECharts {
  return echarts.init(element, undefined, { renderer: 'canvas' });
}

// --- Style tokens -----------------------------------------------------------

/** The selection marker colour: a small red square drawn around selected marks,
 * reused verbatim by the data grid so a selection looks the same in every view. */
export const SELECT_BORDER = '#c53030';
/** Faint grey dashed styling for the lasso rubber-band. */
export const LASSO_STYLE = {
  borderColor: '#999',
  borderType: 'dashed' as const,
  borderWidth: 1,
  color: 'rgba(0, 0, 0, 0.04)'
};
const PRIMARY = '#2b6cb0';

// --- Number / label helpers -------------------------------------------------

/** Format a number for tooltips and in-plot labels with a sensible number of
 * significant figures - no full float precision, no trailing-zero noise. */
export function fmtNum(value: number | null | undefined, sig = 5): string {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const n = Number(value);
  if (n === 0) return '0';
  const abs = Math.abs(n);
  if (abs >= 1e-4 && abs < 1e6) return String(Number(n.toPrecision(sig)));
  return n.toExponential(sig - 1);
}

/** Split a long label across (at most) two lines at a natural break near the
 * middle, so axis labels can stay horizontal. We never rotate axis labels. */
export function wrapAxisLabel(value: string): string {
  const s = String(value ?? '');
  if (s.length <= 8) return s;
  const mid = Math.floor(s.length / 2);
  const separators = new Set([' ', '–', '-', '_', '/', ',']);
  let best = -1;
  for (let i = 1; i < s.length - 1; i++) {
    if (separators.has(s[i]) && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
  }
  if (best > 0) return `${s.slice(0, best + 1)}\n${s.slice(best + 1)}`;
  return `${s.slice(0, mid)}\n${s.slice(mid)}`;
}

/** Shared axis-label config for category axes: always horizontal, auto-thinned,
 * and wrapped to two lines when long. */
export const categoryAxisLabel = {
  rotate: 0,
  hideOverlap: true,
  fontSize: 9,
  lineHeight: 11,
  formatter: wrapAxisLabel
} as const;

// --- Zoom -------------------------------------------------------------------

/** Inside zoom on both axes, plus drag-to-pan. Wheel zoom is handled manually in
 * `PlotChart.svelte` (see {@link zoomedWindow}) because ECharts' built-in wheel
 * zoom steps far too aggressively (up to 1.4x per notch) with no sensitivity
 * knob, so `zoomOnMouseWheel` stays off here. A fresh array per call avoids
 * sharing a mutable option object between charts. */
export function wheelZoom() {
  const common = {
    type: 'inside' as const,
    filterMode: 'none' as const,
    zoomOnMouseWheel: false,
    moveOnMouseMove: true,
    moveOnMouseWheel: false
  };
  return [
    { ...common, xAxisIndex: 0 },
    { ...common, yAxisIndex: 0 }
  ];
}

/** Per-notch wheel zoom factor for the manual handler: <1 zooms in. ~0.9 gives a
 * gentle ~10% step, a fraction of ECharts' built-in 1.2-1.4x. */
export const ZOOM_STEP = 0.9;

/** The new ``[min, max]`` axis window after a wheel zoom centred on ``cursor``.
 * ``factor`` < 1 zooms in (shrinks the window), > 1 zooms out; the data point
 * under the cursor stays fixed so zooming tracks the pointer. */
export function zoomedWindow(
  viewMin: number,
  viewMax: number,
  cursor: number,
  factor: number
): [number, number] {
  const width = viewMax - viewMin;
  if (!(width > 0)) return [viewMin, viewMax];
  const fraction = (cursor - viewMin) / width;
  const newWidth = width * factor;
  return [cursor - fraction * newWidth, cursor + (1 - fraction) * newWidth];
}

// --- Selection helpers ------------------------------------------------------

/** Whether a point is currently selected, given the link state and the dimension
 * the plot links on. */
export function isSelected(
  p: PlotPoint,
  linkBy: LinkDim,
  rows: ReadonlySet<string>,
  cols: ReadonlySet<string>
): boolean {
  const rowHit = p.rowId != null && rows.has(p.rowId);
  const colHit = p.colId != null && cols.has(p.colId);
  if (linkBy === 'row') return rowHit;
  if (linkBy === 'col') return colHit;
  return rowHit || colHit;
}

// --- Scatter ----------------------------------------------------------------

export interface ScatterConfig {
  points: PlotPoint[];
  xName?: string;
  yName?: string;
  symbolSize?: number;
  showLabels?: boolean;
  /** Dashed guide lines through the origin (x=0, y=0). */
  showOrigin?: boolean;
  overlays?: OverlayLine[];
  /** Selected row / column ids, used to draw the red-square markers. */
  selectedRows?: ReadonlySet<string>;
  selectedCols?: ReadonlySet<string>;
  linkBy?: LinkDim;
  /** Whether the lasso/brush component is present (enabled by the caller). */
  brushable?: boolean;
  /** Per-point tooltip HTML; falls back to "label\nx\ny". */
  tooltipHtml?: (p: PlotPoint) => string;
}

const pointLabel = (show: boolean) =>
  ({
    show,
    position: 'right' as const,
    fontSize: 9,
    color: '#444',
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formatter: (p: any) => String(p.name ?? '')
  }) as const;

/** Build a 2-D scatter from `PlotPoint`s. The main scatter is always series 0 so
 * the brush can target it by index; a second, non-interactive overlay series
 * draws red squares around the currently-selected marks. */
export function scatterOption(cfg: ScatterConfig): EChartsOption {
  const {
    points,
    xName = '',
    yName = '',
    symbolSize = 11,
    showLabels = true,
    showOrigin = true,
    overlays = [],
    selectedRows = new Set<string>(),
    selectedCols = new Set<string>(),
    linkBy = 'row',
    brushable = false,
    tooltipHtml
  } = cfg;

  const data = points.map((p) => ({ value: [p.x, p.y], name: p.label }));
  const selected = points.filter((p) => isSelected(p, linkBy, selectedRows, selectedCols));
  const selData = selected.map((p) => [p.x, p.y]);

  const overlaySeries = overlays.map((o) => ({
    type: 'line' as const,
    data: o.points,
    showSymbol: false,
    silent: true,
    z: 1,
    lineStyle: { color: o.color ?? SELECT_BORDER, type: o.dashed ? ('dashed' as const) : ('solid' as const) }
  }));

  const option: EChartsOption = {
    grid: { left: 70, right: 30, top: 30, bottom: 56 },
    dataZoom: wheelZoom(),
    tooltip: {
      trigger: 'item',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (p: any) => {
        const pt = points[p.dataIndex];
        if (!pt) return '';
        if (tooltipHtml) return tooltipHtml(pt);
        return `${pt.label ?? ''}<br/>${xName}: ${fmtNum(pt.x as number)}<br/>${yName}: ${fmtNum(pt.y)}`;
      }
    },
    xAxis: { name: xName, nameLocation: 'middle', nameGap: 30, splitLine: { show: true } },
    yAxis: { name: yName, nameLocation: 'middle', nameGap: 50, splitLine: { show: true } },
    series: [
      {
        type: 'scatter',
        symbolSize,
        z: 2,
        data,
        label: pointLabel(showLabels),
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        markLine: showOrigin
          ? {
              silent: true,
              symbol: 'none',
              lineStyle: { type: 'dashed', color: '#bbb' },
              data: [{ xAxis: 0 }, { yAxis: 0 }]
            }
          : undefined
      },
      ...overlaySeries,
      {
        // Selection overlay: a transparent red square around each selected mark.
        type: 'scatter',
        symbol: 'rect',
        symbolSize: symbolSize + 8,
        z: 3,
        silent: true,
        data: selData,
        itemStyle: { color: 'transparent', borderColor: SELECT_BORDER, borderWidth: 2 }
      }
    ]
  };
  if (brushable) {
    option.brush = {
      xAxisIndex: 0,
      yAxisIndex: 0,
      seriesIndex: 0,
      brushStyle: LASSO_STYLE,
      throttleType: 'debounce',
      throttleDelay: 80,
      removeOnClick: false
    };
  }
  return option;
}

// --- Bar --------------------------------------------------------------------

export interface BarConfig {
  points: PlotPoint[];
  yName?: string;
  xName?: string;
  color?: string;
  limits?: LimitLine[];
  selectedRows?: ReadonlySet<string>;
  selectedCols?: ReadonlySet<string>;
  linkBy?: LinkDim;
}

function limitMarkLine(limits: LimitLine[]) {
  if (!limits.length) return undefined;
  return {
    silent: true,
    symbol: 'none',
    data: limits.map((l) => ({
      yAxis: l.value,
      lineStyle: { color: l.color ?? SELECT_BORDER, type: l.dashed ? ('dashed' as const) : ('solid' as const) },
      label: {
        position: 'insideEndTop' as const,
        color: l.color ?? SELECT_BORDER,
        fontSize: 10,
        formatter: () => l.label ?? fmtNum(l.value)
      }
    }))
  };
}

/** A categorical bar chart from `PlotPoint`s (x = category, y = value). Selected
 * bars get a red outline so bar plots participate in linking too. */
export function barOption(cfg: BarConfig): EChartsOption {
  const {
    points,
    yName = '',
    xName = '',
    color = PRIMARY,
    limits = [],
    selectedRows = new Set<string>(),
    selectedCols = new Set<string>(),
    linkBy = 'row'
  } = cfg;
  const names = points.map((p) => String(p.x));
  const data = points.map((p) => {
    const sel = isSelected(p, linkBy, selectedRows, selectedCols);
    return {
      value: p.y,
      itemStyle: sel ? { color, borderColor: SELECT_BORDER, borderWidth: 2 } : { color }
    };
  });
  return {
    grid: { left: 56, right: 16, top: 24, bottom: xName ? 56 : 48 },
    dataZoom: wheelZoom(),
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmtNum(v as number) },
    xAxis: {
      type: 'category',
      data: names,
      name: xName,
      nameLocation: 'middle',
      nameGap: 38,
      axisLabel: categoryAxisLabel
    },
    yAxis: { type: 'value', name: yName, scale: true },
    series: [{ type: 'bar', data, markLine: limitMarkLine(limits) }]
  };
}

// --- Line / sequence --------------------------------------------------------

export interface LineSeries {
  name?: string;
  /** y values; x comes from `labels` (category) or the index. */
  values: (number | null)[];
  color?: string;
}

export interface LineConfig {
  series: LineSeries[];
  /** Category labels for the x-axis; when omitted, a 1..n index is used. */
  labels?: (string | number)[];
  xName?: string;
  yName?: string;
  showSymbol?: boolean;
  legend?: boolean;
  limits?: LimitLine[];
  /** Indices of points to mark as selected (red squares), for the active series. */
  highlight?: number[];
  /** Optional tooltip override (e.g. to show an identifier per x). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tooltipFormatter?: (params: any) => string;
}

/** A line / sequence plot supporting one or more series, an optional supplied
 * x-axis (e.g. identifiers rather than a bare index), limit lines, and
 * per-point selection highlighting. */
export function lineOption(cfg: LineConfig): EChartsOption {
  const {
    series,
    labels,
    xName = '',
    yName = '',
    showSymbol = false,
    legend = false,
    limits = [],
    highlight = [],
    tooltipFormatter
  } = cfg;
  const n = series[0]?.values.length ?? 0;
  const xData = labels ?? Array.from({ length: n }, (_, i) => i + 1);
  const palette = [PRIMARY, '#2f855a', '#805ad5', '#dd6b20'];
  const hi = new Set(highlight);
  return {
    animation: false,
    grid: { left: 56, right: 16, top: legend ? 36 : 16, bottom: xName ? 44 : 40 },
    dataZoom: wheelZoom(),
    legend: legend ? { top: 4, data: series.map((s) => s.name ?? '') } : undefined,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => fmtNum(v as number),
      formatter: tooltipFormatter
    },
    xAxis: {
      type: 'category',
      data: xData,
      name: xName,
      nameLocation: 'middle',
      nameGap: 28,
      axisLabel: categoryAxisLabel
    },
    yAxis: { type: 'value', name: yName, scale: true },
    series: series.map((s, si) => ({
      name: s.name,
      type: 'line' as const,
      data: s.values.map((v, i) =>
        si === 0 && hi.has(i)
          ? { value: v, symbol: 'rect', symbolSize: 11, itemStyle: { color: 'transparent', borderColor: SELECT_BORDER, borderWidth: 2 } }
          : v
      ),
      showSymbol: showSymbol || (si === 0 && hi.size > 0),
      symbolSize: 7,
      lineStyle: { color: s.color ?? palette[si % palette.length] },
      itemStyle: { color: s.color ?? palette[si % palette.length] },
      markLine: si === 0 ? limitMarkLine(limits) : undefined
    }))
  };
}

// --- Histogram --------------------------------------------------------------

/** Build a frequency histogram from numpy-style counts and bin edges. */
export function histogramOption(counts: number[], edges: number[]): EChartsOption {
  const categories = counts.map((_, i) => {
    const lo = edges[i];
    const hi = edges[i + 1];
    return `${Number(lo).toPrecision(3)}`.concat('–', `${Number(hi).toPrecision(3)}`);
  });
  return {
    animation: false,
    grid: { left: 48, right: 16, top: 16, bottom: 52 },
    dataZoom: wheelZoom(),
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmtNum(v as number) },
    xAxis: { type: 'category', data: categories, axisLabel: categoryAxisLabel },
    yAxis: { type: 'value', name: 'count' },
    series: [{ type: 'bar', data: counts, itemStyle: { color: '#3aa757' }, barWidth: '99%' }]
  };
}

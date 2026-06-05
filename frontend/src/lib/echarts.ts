// Small reusable ECharts module. Keep chart construction here rather than inline
// in pages so plots stay consistent and testable.
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';

export type ScorePoint = [number, number, string];

export function initChart(element: HTMLElement): echarts.ECharts {
  return echarts.init(element, undefined, { renderer: 'canvas' });
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
const categoryAxisLabel = {
  rotate: 0,
  hideOverlap: true,
  fontSize: 9,
  lineHeight: 11,
  formatter: wrapAxisLabel
} as const;

/** Build a 2D scores scatter (one component on each axis), with origin guides. */
export function scoresScatterOption(
  points: ScorePoint[],
  xName: string,
  yName: string
): EChartsOption {
  return {
    grid: { left: 70, right: 30, top: 30, bottom: 56 },
    tooltip: {
      trigger: 'item',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (p: any) =>
        `${p.data[2]}<br/>${xName}: ${Number(p.data[0]).toFixed(3)}` +
        `<br/>${yName}: ${Number(p.data[1]).toFixed(3)}`
    },
    xAxis: {
      name: xName,
      nameLocation: 'middle',
      nameGap: 30,
      splitLine: { show: true }
    },
    yAxis: {
      name: yName,
      nameLocation: 'middle',
      nameGap: 50,
      splitLine: { show: true }
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 11,
        data: points,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#bbb' },
          data: [{ xAxis: 0 }, { yAxis: 0 }]
        }
      }
    ]
  };
}

/** Build a frequency histogram from numpy-style counts and bin edges. */
export function histogramOption(counts: number[], edges: number[]): EChartsOption {
  const categories = counts.map((_, i) => {
    const lo = edges[i];
    const hi = edges[i + 1];
    return `${Number(lo).toPrecision(3)}`.concat('–', `${Number(hi).toPrecision(3)}`);
  });
  return {
    // No animation: the inspector reuses one chart instance across columns, and
    // animating every column switch is distracting.
    animation: false,
    grid: { left: 48, right: 16, top: 16, bottom: 52 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: categoryAxisLabel
    },
    yAxis: { type: 'value', name: 'count' },
    series: [{ type: 'bar', data: counts, itemStyle: { color: '#3aa757' }, barWidth: '99%' }]
  };
}

/** Scores scatter with a Hotelling's T2 confidence ellipse overlay. */
export function scoresEllipseOption(
  points: ScorePoint[],
  ellipseX: number[],
  ellipseY: number[],
  xName: string,
  yName: string
): EChartsOption {
  const ellipse = ellipseX.map((x, i) => [x, ellipseY[i]]);
  return {
    grid: { left: 70, right: 30, top: 30, bottom: 56 },
    tooltip: {
      trigger: 'item',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (p: any) =>
        Array.isArray(p.data) && p.data.length >= 3
          ? `${p.data[2]}<br/>${xName}: ${Number(p.data[0]).toFixed(3)}<br/>${yName}: ${Number(p.data[1]).toFixed(3)}`
          : ''
    },
    xAxis: { name: xName, nameLocation: 'middle', nameGap: 30, splitLine: { show: true } },
    yAxis: { name: yName, nameLocation: 'middle', nameGap: 50, splitLine: { show: true } },
    series: [
      ellipse.length
        ? {
            type: 'line',
            data: ellipse,
            showSymbol: false,
            silent: true,
            lineStyle: { color: '#c53030', type: 'dashed' }
          }
        : { type: 'line', data: [] },
      {
        type: 'scatter',
        symbolSize: 11,
        data: points,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#ddd' },
          data: [{ xAxis: 0 }, { yAxis: 0 }]
        }
      }
    ]
  };
}

/** Loadings scatter with point labels. */
export function loadingsOption(
  points: ScorePoint[],
  xName: string,
  yName: string
): EChartsOption {
  return {
    grid: { left: 70, right: 30, top: 30, bottom: 56 },
    tooltip: { trigger: 'item' },
    xAxis: { name: xName, nameLocation: 'middle', nameGap: 30, splitLine: { show: true } },
    yAxis: { name: yName, nameLocation: 'middle', nameGap: 50, splitLine: { show: true } },
    series: [
      {
        type: 'scatter',
        symbolSize: 9,
        data: points,
        label: {
          show: true,
          position: 'right',
          fontSize: 9,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter: (p: any) => (Array.isArray(p.data) ? p.data[2] : '')
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#ddd' },
          data: [{ xAxis: 0 }, { yAxis: 0 }]
        }
      }
    ]
  };
}

/** Per-observation bar chart with a horizontal control-limit line. */
export function barWithLimitOption(
  names: string[],
  values: number[],
  limit: number,
  yName: string
): EChartsOption {
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 48 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names, axisLabel: categoryAxisLabel },
    yAxis: { type: 'value', name: yName },
    series: [
      {
        type: 'bar',
        data: values,
        itemStyle: { color: '#2b6cb0' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#c53030' },
          data: [{ yAxis: limit, name: 'limit' }]
        }
      }
    ]
  };
}

/** VIP bar chart with a reference line at 1.0. */
export function vipOption(names: string[], values: number[]): EChartsOption {
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 52 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names, axisLabel: categoryAxisLabel },
    yAxis: { type: 'value', name: 'VIP' },
    series: [
      {
        type: 'bar',
        data: values,
        itemStyle: { color: '#805ad5' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#c53030', type: 'dashed' },
          data: [{ yAxis: 1 }]
        }
      }
    ]
  };
}

/** Build a sequence (order-of-acquisition) line plot. */
export function sequenceOption(values: (number | null)[]): EChartsOption {
  return {
    // No animation: switching columns should redraw instantly, not tween.
    animation: false,
    grid: { left: 52, right: 16, top: 16, bottom: 40 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: values.map((_, i) => i + 1), name: 'order' },
    // `scale: true` fits the axis tightly to the data instead of forcing it through 0.
    yAxis: { type: 'value', scale: true },
    series: [
      { type: 'line', data: values, showSymbol: false, lineStyle: { color: '#2b6cb0' } }
    ]
  };
}

export type OneAxisKind = 'bar' | 'line' | 'scatter';

/** A single-component plot: one value per observation/variable along one axis.
 * Used for scores and loadings when a model has only one component, where a 2D
 * scatter would collapse onto a line. The chart type is caller-selectable. */
export function oneComponentOption(
  names: string[],
  values: number[],
  yName: string,
  kind: OneAxisKind = 'bar',
  xName = ''
): EChartsOption {
  const color = '#2b6cb0';
  const series =
    kind === 'bar'
      ? { type: 'bar' as const, data: values, itemStyle: { color } }
      : kind === 'line'
        ? { type: 'line' as const, data: values, symbolSize: 7, lineStyle: { color }, itemStyle: { color } }
        : { type: 'scatter' as const, data: values, symbolSize: 9, itemStyle: { color } };
  return {
    animation: false,
    grid: { left: 60, right: 24, top: 24, bottom: 56 },
    tooltip: { trigger: kind === 'scatter' ? 'item' : 'axis' },
    xAxis: {
      type: 'category',
      data: names,
      name: xName,
      nameLocation: 'middle',
      nameGap: 38,
      axisLabel: categoryAxisLabel
    },
    yAxis: { type: 'value', name: yName, scale: true },
    series: [
      {
        ...series,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#bbb' },
          data: [{ yAxis: 0 }]
        }
      }
    ]
  };
}

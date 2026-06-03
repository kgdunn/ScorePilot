// Small reusable ECharts module. Keep chart construction here rather than inline
// in pages so plots stay consistent and testable.
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';

export type ScorePoint = [number, number, string];

export function initChart(element: HTMLElement): echarts.ECharts {
  return echarts.init(element, undefined, { renderer: 'canvas' });
}

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

import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, CustomChart } from "echarts/charts";
import { GridComponent, TooltipComponent, MarkLineComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import type { ReturnBand } from "../types/market";

echarts.use([LineChart, CustomChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

function useChart(option: EChartsCoreOption, label: string) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    let c: echarts.ECharts | undefined;
    try {
      c = echarts.init(ref.current, undefined, { renderer: "canvas" });
      c.setOption(option);
    } catch {
      /* canvas unavailable (jsdom); text summary next to the chart carries the numbers */
    }
    const onResize = () => c?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      c?.dispose();
    };
  }, [option]);
  return <div ref={ref} className="chart" role="img" aria-label={label} />;
}

const axis = {
  axisLine: { lineStyle: { color: "#3b4660" } },
  axisLabel: { color: "#aab4c8" },
  splitLine: { lineStyle: { color: "#1a2238" } },
};

/** Horizontal p10-p90 range with p50 marker; dashed zero line marks "no change". */
export default function BandChart({ band, label }: { band: ReturnBand; label: string }) {
  const pct = (v: number) => +(v * 100).toFixed(1);
  const { p10, p50, p90 } = band;
  const option: EChartsCoreOption = {
    animation: false,
    grid: { left: 8, right: 16, top: 12, bottom: 24, containLabel: true },
    tooltip: { trigger: "item", formatter: () => `p10 ${pct(p10)}% · p50 ${pct(p50)}% · p90 ${pct(p90)}%` },
    xAxis: {
      type: "value",
      ...axis,
      axisLabel: { ...axis.axisLabel, formatter: "{value}%" },
      min: pct(Math.min(p10, 0)) - 2,
      max: pct(Math.max(p90, 0)) + 2,
    },
    yAxis: { type: "category", data: [""], show: false },
    series: [
      {
        type: "custom",
        data: [[pct(p10), pct(p50), pct(p90)]],
        renderItem: (_p: unknown, api: any) => {
          const y = api.coord([0, 0])[1];
          const a = api.coord([api.value(0), 0])[0];
          const m = api.coord([api.value(1), 0])[0];
          const b = api.coord([api.value(2), 0])[0];
          return {
            type: "group",
            children: [
              { type: "rect", shape: { x: a, y: y - 12, width: b - a, height: 24 }, style: { fill: "rgba(34,211,238,0.28)", stroke: "#22d3ee" } },
              { type: "line", shape: { x1: m, y1: y - 18, x2: m, y2: y + 18 }, style: { stroke: "#a78bfa", lineWidth: 3 } },
            ],
          };
        },
        markLine: { silent: true, symbol: "none", lineStyle: { color: "#64748b", type: "dashed" }, label: { show: false }, data: [{ xAxis: 0 }] },
      },
    ],
  };
  return useChart(option, label);
}

export function SeriesChart({ dates, values, unit, label }: { dates: string[]; values: (number | null)[]; unit: string; label: string }) {
  const option: EChartsCoreOption = {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates, ...axis },
    yAxis: { type: "value", scale: true, name: unit, nameTextStyle: { color: "#aab4c8" }, ...axis },
    series: [{ type: "line", data: values, showSymbol: dates.length < 40, lineStyle: { color: "#22d3ee", width: 2 }, itemStyle: { color: "#22d3ee" } }],
  };
  return useChart(option, label);
}

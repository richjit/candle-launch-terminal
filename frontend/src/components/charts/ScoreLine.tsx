import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { createChart, AreaSeries, type IChartApi, ColorType } from "lightweight-charts";
import type { ScorePoint } from "../../types/pulse";

interface ScoreLineProps {
  scores: ScorePoint[];
  height?: number;
  syncedChart?: IChartApi | null;
}

export interface ScoreLineHandle {
  getChart: () => IChartApi | null;
}

const ScoreLine = forwardRef<ScoreLineHandle, ScoreLineProps>(
  function ScoreLine({ scores, height = 150, syncedChart }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);

    useImperativeHandle(ref, () => ({
      getChart: () => chartRef.current,
    }));

    useEffect(() => {
      if (!containerRef.current) return;

      const chart = createChart(containerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "#12121a" },
          textColor: "#6b7280",
          fontFamily: "'JetBrains Mono', monospace",
        },
        grid: {
          vertLines: { color: "#1e1e2e" },
          horzLines: { color: "#1e1e2e" },
        },
        width: containerRef.current.clientWidth,
        height,
        crosshair: { mode: 0 },
        timeScale: {
          borderColor: "#1e1e2e",
          timeVisible: false,
        },
        rightPriceScale: {
          borderColor: "#1e1e2e",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
      });

      const lineSeries = chart.addSeries(AreaSeries, {
        lineColor: "#f0b90b",
        topColor: "rgba(240, 185, 11, 0.2)",
        bottomColor: "rgba(240, 185, 11, 0.0)",
        lineWidth: 2,
        priceFormat: { type: "custom", formatter: (price: number) => price.toFixed(0) },
      });

      chartRef.current = chart;

      // Crosshair sync deferred — requires series reference across chart boundaries

      if (scores.length > 0) {
        lineSeries.setData(
          scores.map((s) => ({ time: s.time as any, value: s.score }))
        );
      }

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          chart.applyOptions({ width: entry.contentRect.width });
        }
      });
      resizeObserver.observe(containerRef.current);

      return () => {
        resizeObserver.disconnect();
        chart.remove();
        chartRef.current = null;
      };
    }, [height, scores, syncedChart]);

    return (
      <div className="bg-terminal-card border border-terminal-border border-t-0 p-2">
        <div className="text-xs text-terminal-muted mb-1 px-2">Health Score (0–100)</div>
        <div ref={containerRef} />
      </div>
    );
  }
);

export default ScoreLine;

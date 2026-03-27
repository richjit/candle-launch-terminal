import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { createChart, LineSeries, ColorType, type IChartApi } from "lightweight-charts";
import type { ScorePoint } from "../../types/pulse";

interface ScoreLineProps {
  scores: ScorePoint[];
  height?: number;
}

export interface ScoreLineHandle {
  getChart: () => IChartApi | null;
}

function scoreColor(score: number): string {
  if (score >= 70) return "#00e676";
  if (score <= 30) return "#ff1744";
  return "#f0b90b";
}

const ScoreLine = forwardRef<ScoreLineHandle, ScoreLineProps>(
  function ScoreLine({ scores, height = 150 }, ref) {
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

      const lineSeries = chart.addSeries(LineSeries, {
        color: "#f0b90b",
        lineWidth: 2,
        priceFormat: { type: "custom", formatter: (price: number) => price.toFixed(0) },
        lastValueVisible: true,
        priceLineVisible: false,
      });

      chartRef.current = chart;

      if (scores.length > 0) {
        lineSeries.setData(
          scores.map((s) => ({
            time: s.time as any,
            value: s.score,
            color: scoreColor(s.score),
          }))
        );
      }

      // Don't fitContent here — parent controls visible range

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
    }, [height, scores]);

    return (
      <div className="border border-terminal-border border-t-0 p-2 pt-0" style={{ background: "#12121a" }}>
        <div className="text-xs text-terminal-muted mb-1 px-2 pt-1 border-t border-terminal-border/50">
          Health Score (0-100)
        </div>
        <div ref={containerRef} style={{ borderRadius: "0 0 4px 4px", overflow: "hidden" }} />
      </div>
    );
  }
);

export default ScoreLine;

import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";
import type { Candle, ScorePoint } from "../../types/pulse";

export interface CandlestickChartHandle {
  getChart: () => IChartApi | null;
}

interface CandlestickChartProps {
  candles: Candle[];
  scores: ScorePoint[];
  height?: number;
  syncedChart?: IChartApi | null;
}

function scoreToColors(score: number): { line: string; top: string; bottom: string } {
  if (score >= 70) {
    return {
      line: "rgba(0, 230, 118, 0)",
      top: "rgba(0, 230, 118, 0.15)",
      bottom: "rgba(0, 230, 118, 0.02)",
    };
  }
  if (score <= 30) {
    return {
      line: "rgba(255, 23, 68, 0)",
      top: "rgba(255, 23, 68, 0.15)",
      bottom: "rgba(255, 23, 68, 0.02)",
    };
  }
  const t = (score - 30) / 40;
  const r = Math.round(255 * (1 - t));
  const g = Math.round(230 * t);
  return {
    line: `rgba(${r}, ${g}, 68, 0)`,
    top: `rgba(${r}, ${g}, 68, 0.10)`,
    bottom: `rgba(${r}, ${g}, 68, 0.02)`,
  };
}

const CandlestickChart = forwardRef<CandlestickChartHandle, CandlestickChartProps>(
  function CandlestickChart({ candles, scores, height = 400, syncedChart }, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

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
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00e676",
      downColor: "#ff1744",
      borderUpColor: "#00e676",
      borderDownColor: "#ff1744",
      wickUpColor: "#00e676",
      wickDownColor: "#ff1744",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Sync crosshair with the other chart
    // Note: crosshair sync deferred — setCrosshairPosition requires a series reference
    // which we don't have across chart boundaries in this architecture

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
      candleSeriesRef.current = null;
    };
  }, [height, syncedChart]);

  // Update data
  useEffect(() => {
    if (!candleSeriesRef.current || !chartRef.current || candles.length === 0) return;

    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Score-based background gradient via CSS
    if (scores.length > 0) {
      const avgScore = scores.reduce((sum, s) => sum + s.score, 0) / scores.length;
      const colors = scoreToColors(avgScore);

      const container = containerRef.current;
      if (container) {
        container.style.background = `linear-gradient(to bottom, ${colors.top}, ${colors.bottom})`;
      }
    }
  }, [candles, scores]);

  return (
    <div className="bg-terminal-card border border-terminal-border p-2">
      <div ref={containerRef} style={{ borderRadius: "4px", overflow: "hidden" }} />
    </div>
  );
});

export default CandlestickChart;

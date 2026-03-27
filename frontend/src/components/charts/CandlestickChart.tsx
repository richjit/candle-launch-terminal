import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  ColorType,
} from "lightweight-charts";
import type { Candle, ScorePoint } from "../../types/pulse";

export interface CandlestickChartHandle {
  getChart: () => IChartApi | null;
}

interface CandlestickChartProps {
  candles: Candle[];
  scores: ScorePoint[];
  height?: number;
}

function scoreToColor(score: number): string {
  if (score >= 70) return "rgba(0, 230, 118, 0.18)";
  if (score <= 30) return "rgba(255, 23, 68, 0.18)";
  const t = (score - 30) / 40;
  const r = Math.round(255 * (1 - t));
  const g = Math.round(230 * t);
  return `rgba(${r}, ${g}, 68, 0.14)`;
}

function scoreLineColor(score: number): string {
  if (score >= 70) return "#00e676";
  if (score <= 30) return "#ff1744";
  return "#f0b90b";
}

const CandlestickChart = forwardRef<CandlestickChartHandle, CandlestickChartProps>(
  function CandlestickChart({ candles, scores, height = 600 }, ref) {
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
          scaleMargins: { top: 0.02, bottom: 0.28 },
        },
      });

      chartRef.current = chart;

      // 1. Bgcolor histogram
      const bgSeries = chart.addSeries(HistogramSeries, {
        priceScaleId: "bgcolor",
        lastValueVisible: false,
        priceLineVisible: false,
      });
      chart.priceScale("bgcolor").applyOptions({
        visible: false,
        scaleMargins: { top: 0, bottom: 0 },
      });

      // 2. Candlestick series (main right price scale — top 70%)
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#00e676",
        downColor: "#ff1744",
        borderUpColor: "#00e676",
        borderDownColor: "#ff1744",
        wickUpColor: "#00e676",
        wickDownColor: "#ff1744",
      });

      // 3. Pane separator — thin line at the boundary
      const separatorSeries = chart.addSeries(LineSeries, {
        priceScaleId: "separator",
        color: "#2a2a3e",
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      chart.priceScale("separator").applyOptions({
        visible: false,
        scaleMargins: { top: 0.74, bottom: 0.26 },
      });

      // 4. Score line (bottom 23% — its own "pane")
      const scoreSeries = chart.addSeries(LineSeries, {
        priceScaleId: "score",
        color: "#f0b90b",
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: false,
        priceFormat: { type: "custom", formatter: (price: number) => price.toFixed(0) },
      });
      chart.priceScale("score").applyOptions({
        borderColor: "#1e1e2e",
        scaleMargins: { top: 0.78, bottom: 0.02 },
      });

      // Set data
      if (candles.length > 0) {
        candleSeries.setData(
          candles.map((c) => ({
            time: c.time as any,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );
      }

      if (scores.length > 0) {
        bgSeries.setData(
          scores.map((s) => ({
            time: s.time as any,
            value: 1,
            color: scoreToColor(s.score),
          }))
        );

        scoreSeries.setData(
          scores.map((s) => ({
            time: s.time as any,
            value: s.score,
            color: scoreLineColor(s.score),
          }))
        );

        // Separator line at a constant value across all time points
        separatorSeries.setData(
          scores.map((s) => ({
            time: s.time as any,
            value: 1,
          }))
        );
      }

      // Don't fitContent — parent controls visible range

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
    }, [height, candles, scores]);

    return (
      <div className="border border-terminal-border p-2" style={{ background: "#12121a" }}>
        <div ref={containerRef} style={{ borderRadius: "4px", overflow: "hidden" }} />
      </div>
    );
  }
);

export default CandlestickChart;

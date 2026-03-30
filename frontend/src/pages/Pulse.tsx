import { useState, useEffect, useCallback, useRef } from "react";
import PageLayout from "../components/layout/PageLayout";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import RangeSelector from "../components/charts/RangeSelector";
import ScoredFactors from "../components/charts/ScoredFactors";
import { fetchChart, fetchCorrelations } from "../api/pulse";
import type { ChartData, CorrelationsData, ChartRange } from "../types/pulse";

const RANGE_DAYS: Record<ChartRange, number | null> = {
  "30d": 30,
  "90d": 90,
  "1y": 365,
  all: null,
};

export default function Pulse() {
  const [range, setRange] = useState<ChartRange>("90d");
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [correlations, setCorrelations] = useState<CorrelationsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Only TVL, Fear & Greed, and Chain Fees selected by default
  const [excludedFactors, setExcludedFactors] = useState<Set<string>>(
    new Set(["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"])
  );

  const chartRef = useRef<CandlestickChartHandle>(null);

  // Load chart data (all range, with current exclusions)
  const loadChart = useCallback(async (exclude: Set<string>) => {
    try {
      const data = await fetchChart("all", Array.from(exclude));
      setChartData(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart");
    }
  }, []);

  // Initial load
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const defaultExcluded = ["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"];
        const [chart, corr] = await Promise.all([
          fetchChart("all", defaultExcluded),
          fetchCorrelations(),
        ]);
        setChartData(chart);
        setCorrelations(corr);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Set visible range on the chart
  const applyVisibleRange = useCallback((r: ChartRange) => {
    const chart = chartRef.current?.getChart();
    if (!chart) return;

    const days = RANGE_DAYS[r];
    if (!days) {
      chart.timeScale().fitContent();
      return;
    }

    const now = Math.floor(Date.now() / 1000);
    const from = now - days * 86400;
    chart.timeScale().setVisibleRange({ from: from as any, to: now as any });
  }, []);

  // Apply initial visible range after chart mounts
  useEffect(() => {
    if (!chartData) return;
    const timer = setTimeout(() => applyVisibleRange(range), 50);
    return () => clearTimeout(timer);
  }, [chartData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll chart every 60s to pick up new candles and scores
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const chart = await fetchChart("all", Array.from(excludedFactors));
        setChartData(chart);
      } catch {
        // Silently ignore poll failures
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [excludedFactors]);

  const handleRangeChange = useCallback(
    (r: ChartRange) => {
      setRange(r);
      applyVisibleRange(r);
    },
    [applyVisibleRange]
  );

  // Toggle a factor in/out of the score — refetch chart with new exclusions
  const handleToggleFactor = useCallback(
    (name: string) => {
      setExcludedFactors((prev) => {
        const next = new Set(prev);
        if (next.has(name)) {
          next.delete(name);
        } else {
          next.add(name);
        }
        loadChart(next);
        return next;
      });
    },
    [loadChart]
  );

  const currentScore = chartData?.scores?.length
    ? chartData.scores[chartData.scores.length - 1].score
    : null;

  return (
    <PageLayout title="SOL Outlook">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          {currentScore !== null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted uppercase">Health</span>
              <span
                className={`text-2xl font-bold ${
                  currentScore >= 70
                    ? "text-terminal-green"
                    : currentScore <= 30
                      ? "text-terminal-red"
                      : "text-terminal-accent"
                }`}
              >
                {currentScore.toFixed(0)}
              </span>
            </div>
          )}
        </div>
        <RangeSelector selected={range} onChange={handleRangeChange} />
      </div>

      {chartData && chartData.candles.length > 0 && (
        <CandlestickChart
          ref={chartRef}
          candles={chartData.candles}
          scores={chartData.scores}
          height={600}
        />
      )}

      {loading && !chartData && (
        <div className="text-terminal-muted text-center py-16">Loading chart data...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {correlations && (
        <div className="mt-6">
          <ScoredFactors
            factors={correlations.factors}
            excludedFactors={excludedFactors}
            onToggleFactor={handleToggleFactor}
          />
        </div>
      )}
    </PageLayout>
  );
}
